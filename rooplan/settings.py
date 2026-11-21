"""Persist service configuration and protect credentials for the current Windows user."""
import base64
import ctypes
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.8-flash"


def protect(value, decrypt=False):
    if os.name != "nt":
        raise ValueError("当前系统暂不支持保存加密密钥。")

    class Blob(ctypes.Structure):
        _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    operation = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    operation.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                          ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Blob)]
    operation.restype = ctypes.c_int
    buffer = ctypes.create_string_buffer(value)
    source = Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    if not operation(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise ValueError("无法使用 Windows 用户加密保存或读取密钥，请重新填写。")
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(output.data)


class AISettings:
    def __init__(self, folder):
        self.path = Path(folder) / "ai-settings.json"
        self.provider = "qwen"
        self.base = os.getenv("ROOPLAN_BASE_URL") or DEFAULT_BASE
        self.model = os.getenv("ROOPLAN_MODEL") or DEFAULT_MODEL
        self.key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        self.error = ""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if (not isinstance(data, dict) or data.get("provider", "qwen") not in ("qwen", "compatible") or
                    not all(isinstance(data.get(field), str) for field in ("base", "model"))):
                raise ValueError("Invalid service configuration")
            self.provider = data.get("provider", "qwen")
            self.base = data["base"]
            self.model = data["model"]
            self.key = protect(base64.b64decode(data["credential"], validate=True), True).decode() if data.get("credential") else ""
        except FileNotFoundError:
            pass
        except (OSError, ValueError, KeyError, TypeError):
            self.key = ""
            self.error = "无法读取保存的 API 配置，请重新保存。"

    def public(self):
        return dict(provider=self.provider, base=self.base, model=self.model,
                    hasKey=bool(self.key), error=self.error)

    def save(self, provider, base, model, key, clear=False):
        base, model, key = base.strip().rstrip("/"), model.strip(), key.strip()
        parsed = urlsplit(base)
        if provider not in ("qwen", "compatible") or not model:
            raise ValueError("请选择服务并填写模型名称。")
        local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
        if (not parsed.hostname or parsed.scheme not in ("https", "http") or
                (parsed.scheme == "http" and not local) or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("请填写 HTTPS API 基础地址，本地服务可使用 HTTP。")
        if not clear and base != self.base and not key:
            raise ValueError("更换 API 地址时，请填写对应服务的密钥。")
        credential = "" if clear else key or self.key
        if not credential and not clear:
            raise ValueError("请填写 API Key。")
        encrypted = base64.b64encode(protect(credential.encode())).decode() if credential else ""
        data = dict(version=1, provider=provider, base=base, model=model, credential=encrypted)
        temporary = self.path.with_suffix(".tmp")
        try:
            temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            temporary.replace(self.path)
        except OSError:
            raise ValueError("无法保存 API 设置，请检查数据目录权限。") from None
        self.provider, self.base, self.model, self.key = provider, base, model, credential
        self.error = ""
