"""Windows desktop entry point. All web assets are packaged locally."""

import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

from backend.bridge import Bridge
from backend.config import Config
from backend.key_manager import Vault
from backend.migration import preferred_settings_path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "frontend/index.html"


class BundledFiles(QWebEngineUrlRequestInterceptor):
    def __init__(self, parent):
        super().__init__(parent)
        self.files = {
            p.resolve()
            for p in (ROOT / "frontend").rglob("*")
            if p.suffix in {".html", ".css", ".js"}
        }
        self.files.add((ROOT / "assets/icon.png").resolve())

    def interceptRequest(self, info):
        url = info.requestUrl()
        allowed = url.toString() == "qrc:///qtwebchannel/qwebchannel.js"
        if url.isLocalFile():
            allowed = Path(url.toLocalFile()).resolve() in self.files
        info.block(not allowed)


class AppPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, kind, main_frame):
        if (
            main_frame
            and url.isLocalFile()
            and Path(url.toLocalFile()).resolve() == INDEX
        ):
            return True
        if (
            main_frame
            and kind == self.NavigationType.NavigationTypeLinkClicked
            and url.scheme() in {"https", "http"}
            and url.host()
            and not url.userInfo()
        ):
            QDesktopServices.openUrl(url)
        return False

    def createWindow(self, _kind):
        return None


class Window(QMainWindow):
    def __init__(self, config=None, vault=None, transport=None):
        super().__init__()
        self.setWindowTitle("MULTI-AI")
        self.setWindowIcon(QIcon(str(ROOT / "assets/icon.png")))
        self.setMinimumSize(410, 360)
        area = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1240, area.width()), min(820, area.height()))
        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.profile = QWebEngineProfile(self)
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        self.filter = BundledFiles(self.profile)
        self.profile.setUrlRequestInterceptor(self.filter)
        self.page = AppPage(self.profile, self.view)
        self.view.setPage(self.page)
        self.page.permissionRequested.connect(lambda permission: permission.deny())
        self.profile.downloadRequested.connect(lambda download: download.cancel())
        for attr in (
            "LocalStorageEnabled",
            "JavascriptCanOpenWindows",
            "JavascriptCanAccessClipboard",
            "JavascriptCanPaste",
            "LocalContentCanAccessRemoteUrls",
            "PluginsEnabled",
            "WebGLEnabled",
            "HyperlinkAuditingEnabled",
            "DnsPrefetchEnabled",
            "FullScreenSupportEnabled",
            "NavigateOnDropEnabled",
        ):
            self.page.settings().setAttribute(
                getattr(QWebEngineSettings.WebAttribute, attr), False
            )
        self.page.setBackgroundColor(Qt.GlobalColor.black)
        if config is None:
            config_dir = Path(QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppConfigLocation
            ))
            # Migrate user preferences from older installs without overwriting them.
            config_file = preferred_settings_path(
                config_dir / "settings.json",
                config_dir.with_name("MULTIAI") / "settings.json",
            )
            config = Config(config_file)
        self.bridge = Bridge(self, config, vault or Vault(), transport)
        self.channel = QWebChannel(self.page)
        self.channel.registerObject("desktop", self.bridge)
        self.page.setWebChannel(self.channel)
        self.set_zoom(config.data["scale"] / 100)
        self.view.load(QUrl.fromLocalFile(str(INDEX)))

    def set_zoom(self, scale):
        self.view.setZoomFactor(scale)

    def closeEvent(self, event):
        if not self.bridge.closed:
            self.bridge.close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MULTI-AI")
    app.setApplicationVersion("1.0.0")
    app.setStyle("Fusion")
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    window = Window()
    window.show()
    app.aboutToQuit.connect(
        lambda: window.bridge.close() if not window.bridge.closed else None
    )
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
