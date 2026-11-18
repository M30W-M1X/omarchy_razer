import QtQuick
import qs.Commons
import qs.Commons as Commons
import qs.Ui

// Geometric Razer Chroma prism emblem with a live RGB status dot that
// mirrors the active keyboard/mouse color and pulses during AI animations.
Item {
  id: root

  property real iconSize: Style.font.icon
  property color color: Commons.Color.foreground
  property color liveColor: Commons.Color.accent
  property bool active: false
  property bool aiActive: false

  width: iconSize
  height: iconSize
  implicitWidth: iconSize
  implicitHeight: iconSize

  onColorChanged: glyphCanvas.requestPaint()
  onActiveChanged: glyphCanvas.requestPaint()
  onIconSizeChanged: glyphCanvas.requestPaint()

  Canvas {
    id: glyphCanvas
    anchors.fill: parent
    antialiasing: true

    onPaint: {
      var ctx = getContext("2d")
      ctx.clearRect(0, 0, width, height)

      var s = Math.min(width, height)
      var cx = width / 2
      var cy = height / 2
      var rOuter = s * 0.41
      var rInner = s * 0.14

      ctx.strokeStyle = root.color
      ctx.fillStyle = root.color
      ctx.lineWidth = Math.max(1.5, s * 0.105)
      ctx.lineCap = "round"
      ctx.lineJoin = "round"

      // Three intertwined curved blades (120 deg apart) inspired by Razer's triskelion
      for (var i = 0; i < 3; i++) {
        var a0 = (i * 120 - 90) * Math.PI / 180
        var aMid = (i * 120 - 30) * Math.PI / 180
        var aTip = (i * 120 + 18) * Math.PI / 180

        var x0 = cx + Math.cos(a0) * rInner
        var y0 = cy + Math.sin(a0) * rInner
        var xm = cx + Math.cos(aMid) * (rOuter * 0.96)
        var ym = cy + Math.sin(aMid) * (rOuter * 0.96)
        var xt = cx + Math.cos(aTip) * (rOuter * 0.72)
        var yt = cy + Math.sin(aTip) * (rOuter * 0.72)

        ctx.beginPath()
        ctx.moveTo(x0, y0)
        ctx.quadraticCurveTo(xm, ym, xt, yt)
        ctx.stroke()
      }

      // Crisp center jewel
      ctx.beginPath()
      ctx.arc(cx, cy, Math.max(1.4, s * 0.095), 0, Math.PI * 2)
      ctx.fill()
    }
  }

  // Live RGB status dot reflecting actual keyboard/AI color
  BorderSurface {
    id: statusDot
    visible: root.active
    width: Math.max(6, parent.width * 0.36)
    height: width
    radius: width / 2
    color: root.liveColor
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    anchors.rightMargin: -width * 0.10
    anchors.bottomMargin: -height * 0.06
    borderSpec: Border.flat(Commons.Color.popups.background, 1.2)

    SequentialAnimation on opacity {
      running: root.active && root.aiActive
      loops: Animation.Infinite
      NumberAnimation { from: 1.0; to: 0.3; duration: Math.max(1, Style.duration(260)); easing.type: Easing.OutCubic }
      NumberAnimation { from: 0.3; to: 1.0; duration: Math.max(1, Style.duration(260)); easing.type: Easing.OutCubic }
    }
  }
}
