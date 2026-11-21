import QtQuick

Canvas {
    id: icon
    property string name: ""
    property color ink: "#687d6b"
    implicitWidth: 20
    implicitHeight: 20
    antialiasing: true
    onNameChanged: requestPaint()
    onInkChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    function strokePath(context, points) {
        context.beginPath()
        context.moveTo(points[0][0], points[0][1])
        for (let i = 1; i < points.length; i++) context.lineTo(points[i][0], points[i][1])
        context.stroke()
    }
    function windowFrame(context) {
        context.beginPath()
        context.moveTo(5,4)
        context.lineTo(19,4)
        context.quadraticCurveTo(21,4,21,6)
        context.lineTo(21,18)
        context.quadraticCurveTo(21,20,19,20)
        context.lineTo(5,20)
        context.quadraticCurveTo(3,20,3,18)
        context.lineTo(3,6)
        context.quadraticCurveTo(3,4,5,4)
        context.stroke()
    }
    onPaint: {
        let context = getContext("2d")
        context.reset()
        context.clearRect(0,0,width,height)
        context.scale(width/24,height/24)
        context.strokeStyle = ink
        context.fillStyle = ink
        context.lineWidth = 1.8
        context.lineCap = "round"
        context.lineJoin = "round"
        switch (name) {
        case "chevron-left":
            strokePath(context, [[14,7],[9,12],[14,17]])
            break
        case "chevron-right":
            strokePath(context, [[10,7],[15,12],[10,17]])
            break
        case "chevron-down":
            strokePath(context, [[7,10],[12,15],[17,10]])
            break
        case "fold":
            windowFrame(context)
            strokePath(context, [[16,4],[16,20]])
            strokePath(context, [[8,9],[11,12],[8,15]])
            break
        case "pin":
            strokePath(context, [[8,3],[16,3],[15,8],[18,12],[18,14],[6,14],[6,12],[9,8],[8,3]])
            strokePath(context, [[12,14],[12,21]])
            break
        case "more":
            for (let x of [5,12,19]) {
                context.beginPath()
                context.arc(x,12,1.35,0,Math.PI*2)
                context.fill()
            }
            break
        case "plus":
            strokePath(context, [[5,12],[19,12]])
            strokePath(context, [[12,5],[12,19]])
            break
        case "check":
            strokePath(context, [[5,12],[10,17],[19,7]])
            break
        case "search":
            context.beginPath()
            context.arc(10.5,10.5,5.5,0,Math.PI*2)
            context.stroke()
            strokePath(context, [[15,15],[20,20]])
            break
        case "bell":
            context.beginPath()
            context.moveTo(5,17)
            context.quadraticCurveTo(7,15,7,11)
            context.quadraticCurveTo(7,5,12,5)
            context.quadraticCurveTo(17,5,17,11)
            context.quadraticCurveTo(17,15,19,17)
            context.closePath()
            context.stroke()
            strokePath(context, [[10,20],[14,20]])
            break
        case "settings":
            strokePath(context, [[5,7],[19,7]])
            strokePath(context, [[5,12],[19,12]])
            strokePath(context, [[5,17],[19,17]])
            for (let p of [[9,7],[15,12],[10,17]]) {
                context.beginPath()
                context.arc(p[0],p[1],1.7,0,Math.PI*2)
                context.fill()
            }
            break
        case "exit":
            strokePath(context, [[12,5],[5,5],[5,19],[12,19]])
            strokePath(context, [[10,12],[20,12],[16,8]])
            strokePath(context, [[20,12],[16,16]])
            break
        case "inbox":
            strokePath(context, [[3,14],[6,5],[18,5],[21,14],[21,19],[3,19],[3,14],
                                 [8,14],[10,16],[14,16],[16,14],[21,14]])
            break
        case "close":
            strokePath(context, [[7,7],[17,17]])
            strokePath(context, [[17,7],[7,17]])
            break
        case "image":
            windowFrame(context)
            strokePath(context, [[3,16],[9,10],[14,15],[17,12],[21,16]])
            context.beginPath()
            context.arc(15,8,1,0,Math.PI*2)
            context.fill()
            break
        case "calendar":
            windowFrame(context)
            strokePath(context, [[3,9],[21,9]])
            strokePath(context, [[8,2],[8,6]])
            strokePath(context, [[16,2],[16,6]])
            strokePath(context, [[10,13],[14,13],[14,17],[10,17],[10,13]])
            break
        case "loader":
            context.beginPath()
            context.arc(12,12,8,-Math.PI/2,Math.PI)
            context.stroke()
            break
        }
    }
    transform: Rotation {
        id: spinner
        origin.x: icon.width/2
        origin.y: icon.height/2
        NumberAnimation on angle {
            running: icon.name === "loader" && icon.visible
            from: 0; to: 360; duration: 1100; loops: Animation.Infinite
            onStopped: spinner.angle = 0
        }
    }
}
