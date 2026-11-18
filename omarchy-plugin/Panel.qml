import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import qs.Ui

Panel {
  id: root
  moduleName: "razer.chroma"
  ipcTarget: "razer.chroma"

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Commons.Translations {
    id: strings
    directory: Qt.resolvedUrl("i18n")
  }

  readonly property string pluginDir: decodeURIComponent(String(Qt.resolvedUrl(".")).replace(/^file:\/\//, "")).replace(/\/$/, "")
  readonly property string helperPath: pluginDir !== "" ? pluginDir + "/helper.py" : ""
  readonly property int pollMs: Math.max(1000, Math.min(30000, Number(setting("refreshIntervalSec", 2)) * 1000))

  // Daemon snapshot state
  property bool daemonActive: false
  property bool openrazerConnected: false
  property string errorText: ""
  property bool lightsEnabled: true
  property string currentMode: "theme"
  property string currentColor: "#7fbbb3"
  property string keyboardColor: ""
  property string mouseColor: ""
  property int brightness: 85
  property bool aiReactive: true
  property string palette: "omarchy-theme"
  property color liveColor: Commons.Color.accent
  property bool aiActive: false
  property string aiState: "idle"
  property string aiSource: ""
  property string aiTool: ""
  property string aiDetail: ""
  property var devices: []
  property var swatches: []

  // Local UI state
  property string colorTarget: "all"
  property bool busy: false
  property string hexDraft: "#7fbbb3"
  property bool hexInputFocused: false

  readonly property color foreground: bar ? bar.foreground : Commons.Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property color barIconColor: (daemonActive && lightsEnabled) ? barForeground : Qt.darker(barForeground, 1.55)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  // Neutralize markup before passing dynamic text to Omarchy-owned tooltip sinks
  function sanitizePlainText(input) {
    return String(input || "").replace(/[<>]/g, "").slice(0, 140)
  }

  function validHex(s) {
    return /^#?[0-9a-fA-F]{6}$/.test(String(s || "").trim())
  }

  function formatAiState(st) {
    var map = {
      "idle": "Idle",
      "session_start": "Session Start",
      "thinking": "Thinking",
      "tool_command": "Running Command",
      "tool_edit": "Editing Code",
      "tool_read": "Scanning / Reading",
      "tool_agent": "Running Subagents",
      "error": "Error Alert",
      "attention": "Needs Attention",
      "complete": "Task Complete"
    }
    return map[st] || String(st || "Idle")
  }

  readonly property string statusSubtitle: {
    if (!daemonActive) return strings.t("status.daemonOffline")
    if (!openrazerConnected) return strings.t("status.noDevices")
    if (!lightsEnabled || currentMode === "off") return strings.t("status.off")
    if (aiActive) {
      var label = formatAiState(aiState).toUpperCase()
      if (aiSource !== "" && aiSource !== "preview") label += " · " + aiSource.toUpperCase()
      return strings.t("status.aiActive").arg(label)
    }
    return currentMode.toUpperCase() + " · " + strings.tn("status.devices", devices.length).arg(Commons.I18n.formatNumber(devices.length))
  }

  readonly property string barTooltip: {
    var base = strings.t("plugin.title") + " · " + statusSubtitle
    return sanitizePlainText(base)
  }

  readonly property string activeTargetHex: {
    if (colorTarget === "keyboard" && keyboardColor !== "") return keyboardColor
    if (colorTarget === "mouse" && mouseColor !== "") return mouseColor
    return currentColor
  }

  function applySnapshot(raw) {
    try {
      var data = JSON.parse(raw)
      if (!data || typeof data !== "object") return
      daemonActive = data.daemonActive === true
      openrazerConnected = data.openrazerConnected === true
      errorText = String(data.error || "")
      devices = Array.isArray(data.devices) ? data.devices.slice(0, 12) : []
      if (Array.isArray(data.swatches) && data.swatches.length > 0) {
        swatches = data.swatches.slice(0, 20)
      }
      if (data.config && typeof data.config === "object") {
        lightsEnabled = data.config.enabled !== false
        currentMode = String(data.config.mode || "theme")
        currentColor = String(data.config.color || "#7fbbb3")
        keyboardColor = String(data.config.keyboardColor || "")
        mouseColor = String(data.config.mouseColor || "")
        brightness = Math.max(0, Math.min(100, Number(data.config.brightness !== undefined ? data.config.brightness : 85)))
        aiReactive = data.config.aiReactive !== false
        palette = String(data.config.palette || "omarchy-theme")
      }
      if (data.liveColor && validHex(data.liveColor)) {
        liveColor = data.liveColor
      }
      if (data.ai && typeof data.ai === "object") {
        aiActive = data.ai.active === true
        aiState = String(data.ai.state || "idle")
        aiSource = String(data.ai.source || "")
        aiTool = String(data.ai.tool || "")
        aiDetail = String(data.ai.detail || "")
      } else {
        aiActive = false
        aiState = "idle"
      }
      if (!root.hexInputFocused && validHex(activeTargetHex)) {
        hexDraft = activeTargetHex
      }
    } catch (e) {}
  }

  function refresh() {
    if (helperPath === "" || statusProc.running) return
    statusProc.command = ["python3", helperPath, "status"]
    statusProc.running = true
  }

  function runAction(args) {
    if (helperPath === "" || actionProc.running) return
    busy = true
    actionProc.command = ["python3", helperPath].concat(args)
    actionProc.running = true
  }

  function applyColorHex(hexVal) {
    var clean = String(hexVal || "").trim()
    if (!validHex(clean)) return
    if (clean.charAt(0) !== "#") clean = "#" + clean
    hexDraft = clean.toLowerCase()
    runAction(["color", hexDraft, colorTarget])
  }

  Component.onCompleted: Qt.callLater(refresh)
  onOpenedChanged: if (opened) refresh()

  Timer {
    id: pollTimer
    interval: root.opened ? Math.min(root.pollMs, 1200) : root.pollMs
    repeat: true
    running: root.helperPath !== ""
    onTriggered: root.refresh()
  }

  Process {
    id: statusProc
    stdout: StdioCollector {
      onStreamFinished: root.applySnapshot(text)
    }
  }

  Process {
    id: actionProc
    stdout: StdioCollector {
      onStreamFinished: {
        root.busy = false
        root.applySnapshot(text)
      }
    }
    onExited: root.busy = false
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    tooltipText: root.opened ? "" : root.barTooltip
    iconComponent: Component { Item {} }

    RazerIcon {
      x: (button.width - width) / 2
      y: (button.height - height) / 2
      iconSize: button.iconSize
      color: root.barIconColor
      liveColor: root.liveColor
      active: root.daemonActive && root.lightsEnabled && root.currentMode !== "off"
      aiActive: root.aiActive
    }

    onPressed: function(b) {
      if (b === Qt.RightButton) root.runAction(["power", root.lightsEnabled ? "off" : "on"])
      else if (b === Qt.MiddleButton) root.runAction(["rescan"])
      else root.toggle()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: panel.loadedContent
    contentWidth: panel.fittedContentWidth(Style.space(368))
    contentHeight: panel.fittedContentHeight(panel.loadedContentHeight)

    content: PanelKeyCatcher {
      id: keyCatcher
      implicitHeight: column.implicitHeight
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Column {
        id: column
        anchors.fill: parent
        spacing: Style.space(12)

        // Hero header
        Item {
          width: parent.width
          implicitHeight: Math.max(heroIcon.height, heroLabels.implicitHeight, powerSwitch.implicitHeight)

          RazerIcon {
            id: heroIcon
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            iconSize: Style.font.display
            color: root.foreground
            liveColor: root.liveColor
            active: root.daemonActive && root.lightsEnabled && root.currentMode !== "off"
            aiActive: root.aiActive
            opacity: root.lightsEnabled ? 1.0 : 0.45
          }

          ToggleSwitch {
            id: powerSwitch
            checked: root.daemonActive && root.lightsEnabled && root.currentMode !== "off"
            busy: root.busy
            foreground: root.foreground
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            onToggled: {
              if (!root.daemonActive) root.runAction(["start"])
              else root.runAction(["power", root.lightsEnabled ? "off" : "on"])
            }
          }

          Column {
            id: heroLabels
            anchors.left: heroIcon.right
            anchors.leftMargin: Style.space(12)
            anchors.right: powerSwitch.left
            anchors.rightMargin: Style.space(10)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.space(2)

            Text {
              text: strings.t("plugin.title")
              textFormat: Text.PlainText
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.title
              font.bold: true
              elide: Text.ElideRight
              width: parent.width
            }

            Text {
              text: root.statusSubtitle
              textFormat: Text.PlainText
              color: root.aiActive ? Commons.Color.accent : root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              font.bold: true
              font.letterSpacing: 1.0
              elide: Text.ElideRight
              width: parent.width
            }
          }
        }

        PanelSeparator { foreground: root.foreground }

        // Connected Devices or Setup Hint
        Column {
          width: parent.width
          spacing: Style.space(6)

          Row {
            width: parent.width
            spacing: Style.space(8)

            PanelSectionHeader {
              text: strings.t("section.devices")
              foreground: root.foreground
              fontFamily: root.fontFamily
              width: parent.width - rescanBtn.implicitWidth - Style.space(8)
              anchors.verticalCenter: parent.verticalCenter
            }

            Button {
              id: rescanBtn
              text: root.daemonActive ? strings.t("button.rescan") : strings.t("button.startDaemon")
              foreground: root.foreground
              fontFamily: root.fontFamily
              fontSize: Style.font.caption
              bordered: true
              onClicked: root.runAction([root.daemonActive ? "rescan" : "start"])
            }
          }

          Repeater {
            model: root.devices
            delegate: Row {
              required property var modelData
              width: parent.width
              spacing: Style.space(8)

              Rectangle {
                width: Style.space(10)
                height: Style.space(10)
                radius: width / 2
                color: root.validHex(modelData.lastColor) ? String(modelData.lastColor) : root.liveColor
                anchors.verticalCenter: parent.verticalCenter
              }

              Text {
                text: String(modelData.name || "Razer Device")
                textFormat: Text.PlainText
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.bodySmall
                elide: Text.ElideRight
                width: parent.width - Style.space(96)
                anchors.verticalCenter: parent.verticalCenter
              }

              Text {
                text: {
                  var parts = []
                  if (modelData.hasMatrix) parts.push(String(modelData.matrixRows) + "x" + String(modelData.matrixCols))
                  if (modelData.battery !== null && modelData.battery !== undefined) {
                    parts.push(Commons.I18n.formatNumber(Number(modelData.battery)) + "%")
                  }
                  if (parts.length === 0) parts.push(String(modelData.type || ""))
                  return parts.join(" · ")
                }
                textFormat: Text.PlainText
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                horizontalAlignment: Text.AlignRight
                width: Style.space(76)
                anchors.verticalCenter: parent.verticalCenter
              }
            }
          }

          Text {
            visible: root.devices.length === 0
            text: root.errorText !== "" ? root.errorText : strings.t("hint.openrazer")
            textFormat: Text.PlainText
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
            width: parent.width
          }
        }

        PanelSeparator { foreground: root.foreground }

        // Lighting Mode selector
        Column {
          width: parent.width
          spacing: Style.space(6)

          PanelSectionHeader {
            text: strings.t("section.mode")
            foreground: root.foreground
            fontFamily: root.fontFamily
          }

          Flow {
            width: parent.width
            spacing: Style.space(6)

            Repeater {
              model: [
                { value: "theme", label: strings.t("mode.theme") },
                { value: "static", label: strings.t("mode.static") },
                { value: "breath", label: strings.t("mode.breath") },
                { value: "wave", label: strings.t("mode.wave") },
                { value: "spectrum", label: strings.t("mode.spectrum") },
                { value: "reactive", label: strings.t("mode.reactive") },
                { value: "starlight", label: strings.t("mode.starlight") },
                { value: "off", label: strings.t("mode.off") }
              ]
              delegate: Button {
                required property var modelData
                text: modelData.label
                selected: root.currentMode === modelData.value
                bordered: true
                foreground: root.foreground
                fontFamily: root.fontFamily
                fontSize: Style.font.caption
                onClicked: root.runAction(["mode", modelData.value])
              }
            }
          }
        }

        // Color Swatches & Custom Hex Picker
        Column {
          width: parent.width
          spacing: Style.space(8)

          Row {
            width: parent.width
            spacing: Style.space(8)

            PanelSectionHeader {
              text: strings.t("section.color")
              foreground: root.foreground
              fontFamily: root.fontFamily
              width: parent.width - targetGroup.implicitWidth - Style.space(8)
              anchors.verticalCenter: parent.verticalCenter
            }

            ButtonGroup {
              id: targetGroup
              value: root.colorTarget
              foreground: root.foreground
              fontFamily: root.fontFamily
              fontSize: Style.font.caption
              focusable: false
              options: [
                { value: "all", label: strings.t("target.all") },
                { value: "keyboard", label: strings.t("target.keyboard") },
                { value: "mouse", label: strings.t("target.mouse") }
              ]
              onChanged: function(v) {
                root.colorTarget = v
                if (root.validHex(root.activeTargetHex)) root.hexDraft = root.activeTargetHex
              }
            }
          }

          // 8-column swatch grid (Row 1 = active Omarchy theme, Row 2 = vivid RGB presets)
          Grid {
            width: parent.width
            columns: 8
            spacing: Style.space(6)

            Repeater {
              model: root.swatches.length > 0 ? root.swatches : [
                { label: "Accent", hex: "#7fbbb3" },
                { label: "Red", hex: "#e67e80" },
                { label: "Orange", hex: "#e09d7f" },
                { label: "Yellow", hex: "#dbbc7f" },
                { label: "Green", hex: "#a7c080" },
                { label: "Cyan", hex: "#83c092" },
                { label: "Blue", hex: "#7fbbb3" },
                { label: "Magenta", hex: "#d699b6" },
                { label: "Razer", hex: "#44d62c" },
                { label: "Fire", hex: "#ff4500" },
                { label: "Arcane", hex: "#9b4dff" },
                { label: "Crimson", hex: "#ff1744" },
                { label: "Gold", hex: "#ffc400" },
                { label: "Ice", hex: "#00e5ff" },
                { label: "Sakura", hex: "#ff4da6" },
                { label: "White", hex: "#ffffff" }
              ]

              delegate: BorderSurface {
                required property var modelData
                readonly property string hexVal: String(modelData.hex || "#7fbbb3").toLowerCase()
                readonly property bool isSelected: root.activeTargetHex.toLowerCase() === hexVal && root.currentMode !== "theme"
                width: Math.floor((parent.width - 7 * Style.space(6)) / 8)
                height: Style.space(22)
                radius: Style.cornerRadius
                color: hexVal
                borderSpec: isSelected
                  ? Border.flat(root.foreground, 2)
                  : Border.flat(Qt.rgba(1, 1, 1, 0.18), 1)
                scale: swatchMouse.containsMouse ? 1.08 : 1.0

                Behavior on scale {
                  NumberAnimation { duration: Style.duration(110); easing.type: Easing.OutCubic }
                }

                MouseArea {
                  id: swatchMouse
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.applyColorHex(parent.hexVal)
                }
              }
            }
          }

          Row {
            width: parent.width
            spacing: Style.space(8)

            Rectangle {
              width: Style.space(24)
              height: hexInput.implicitHeight
              radius: Style.cornerRadius
              color: root.validHex(hexInput.text) ? (hexInput.text.charAt(0) === "#" ? hexInput.text : "#" + hexInput.text) : root.liveColor
              border.color: Qt.rgba(1, 1, 1, 0.25)
              border.width: 1
            }

            TextField {
              id: hexInput
              text: root.hexDraft
              placeholderText: "#7fbbb3"
              foreground: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              width: parent.width - Style.space(24) - applyHexBtn.implicitWidth - Style.space(16)
              onActiveFocusChanged: root.hexInputFocused = activeFocus
              onAccepted: root.applyColorHex(text)
            }

            Button {
              id: applyHexBtn
              text: strings.t("button.apply")
              enabled: root.validHex(hexInput.text)
              bordered: true
              foreground: root.foreground
              fontFamily: root.fontFamily
              fontSize: Style.font.caption
              onClicked: root.applyColorHex(hexInput.text)
            }
          }
        }

        // Brightness Slider
        Column {
          width: parent.width
          spacing: Style.space(4)

          Row {
            width: parent.width

            PanelSectionHeader {
              text: strings.t("section.brightness")
              foreground: root.foreground
              fontFamily: root.fontFamily
              width: parent.width - brightLabel.implicitWidth
            }

            Text {
              id: brightLabel
              text: Commons.I18n.formatNumber(Math.round(brightSlider.liveValue)) + "%"
              textFormat: Text.PlainText
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              font.bold: true
            }
          }

          PanelSlider {
            id: brightSlider
            width: parent.width
            bar: root.bar
            minimum: 0
            maximum: 100
            step: 5
            integer: true
            value: root.brightness
            onReleased: function(v) {
              root.brightness = Math.round(v)
              root.runAction(["brightness", String(Math.round(v))])
            }
          }
        }

        PanelSeparator { foreground: root.foreground }

        // AI Reactive (Diablo Mode) section
        Column {
          width: parent.width
          spacing: Style.space(8)

          Row {
            width: parent.width
            spacing: Style.space(8)

            PanelSectionHeader {
              text: strings.t("section.ai")
              foreground: root.foreground
              fontFamily: root.fontFamily
              width: parent.width - aiToggle.implicitWidth - Style.space(8)
              anchors.verticalCenter: parent.verticalCenter
            }

            ToggleSwitch {
              id: aiToggle
              checked: root.aiReactive
              foreground: root.foreground
              onToggled: root.runAction(["reactive", root.aiReactive ? "off" : "on"])
            }
          }

          Row {
            width: parent.width
            spacing: Style.space(8)

            Rectangle {
              width: Style.space(8)
              height: Style.space(8)
              radius: width / 2
              color: root.aiActive ? root.liveColor : root.dim
              anchors.verticalCenter: parent.verticalCenter
            }

            Text {
              text: {
                if (!root.aiActive) return strings.t("ai.idle")
                var info = root.formatAiState(root.aiState)
                if (root.aiTool !== "" && root.aiTool !== root.aiState) info += " (" + root.aiTool + ")"
                return strings.t("ai.activeLabel").arg(info)
              }
              textFormat: Text.PlainText
              color: root.aiActive ? root.foreground : root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              elide: Text.ElideRight
              width: parent.width - Style.space(18)
            }
          }

          ButtonGroup {
            width: parent.width
            value: root.palette
            foreground: root.foreground
            fontFamily: root.fontFamily
            fontSize: Style.font.caption
            focusable: false
            options: [
              { value: "omarchy-theme", label: strings.t("palette.omarchy") },
              { value: "diablo", label: strings.t("palette.diablo") },
              { value: "cyberpunk", label: strings.t("palette.cyberpunk") }
            ]
            onChanged: function(v) { root.runAction(["palette", v]) }
          }

          Column {
            width: parent.width
            spacing: Style.space(4)

            Text {
              text: strings.t("section.preview")
              textFormat: Text.PlainText
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              font.bold: true
            }

            Flow {
              width: parent.width
              spacing: Style.space(6)

              Repeater {
                model: [
                  { state: "thinking", label: strings.t("preview.thinking") },
                  { state: "tool_command", label: strings.t("preview.tool_command") },
                  { state: "tool_edit", label: strings.t("preview.tool_edit") },
                  { state: "error", label: strings.t("preview.error") },
                  { state: "complete", label: strings.t("preview.complete") }
                ]
                delegate: Button {
                  required property var modelData
                  text: modelData.label
                  selected: root.aiActive && root.aiState === modelData.state
                  bordered: true
                  foreground: root.foreground
                  fontFamily: root.fontFamily
                  fontSize: Style.font.caption
                  onClicked: root.runAction(["preview", modelData.state])
                }
              }
            }
          }
        }
      }
    }
  }
}
