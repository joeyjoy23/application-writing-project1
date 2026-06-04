"""兼容层：实现已并入 ui.sidebar，请优先从该模块导入。"""

from ui.sidebar import inject_sidebar_collapse_dock, render_sidebar_workspace_topbar

__all__ = ["inject_sidebar_collapse_dock", "render_sidebar_workspace_topbar"]
