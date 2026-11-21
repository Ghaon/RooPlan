# RooPlan Windows 安装包

在 Windows x64 上使用 Python 3.13 和 Inno Setup 7 构建。打包脚本通过 PyInstaller 将程序、Python、Qt 和 QML 资源放到同一个目录，再由 Inno Setup 生成 `.exe` 安装包。

```powershell
python -m pip install PySide6-Essentials==6.9.2 PyInstaller==6.22.3
.\packaging\build-windows.ps1 -Version 0.1.0-preview.1 -InnoCompiler 'C:\Program Files\Inno Setup 7\ISCC.exe'
```

使用虚拟环境时，可以通过 `-Python .\.venv\Scripts\python.exe` 选择解释器。脚本会输出 `build\windows-…\release\` 下安装包的完整路径。

安装仅面向当前用户。启动入口是开始菜单里的 RooPlan。日程和 AI 连接设置保存在 `%LOCALAPPDATA%\RooPlan`，卸载安装包会保留这个目录。由于源码版也使用同一个默认目录，同一用户可以继续使用已有日程。

将对应源码提交到 GitHub 后，进入 **Releases → Draft a new release**，创建指向该提交的 `v0.1.0-preview.1` 标签，把安装包作为附件上传，并勾选 **Set as a pre-release**。安装包文件应放在 Release 附件中。
