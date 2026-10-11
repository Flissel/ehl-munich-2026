"""Project start-up script (run automatically by the Python plugin).

Starts the BMW Studio viewer runtime only when the project is launched as the viewer
(`-game -BMWViewer`); the editor and build commandlets are left untouched.
"""
import unreal

_cmdline = unreal.SystemLibrary.get_command_line()
if "-bmwviewer" in _cmdline.lower():
    try:
        from bmw_viewer import runtime
        runtime.start(_cmdline)
    except Exception as exc:  # surface the reason in the log instead of failing silently
        unreal.log_error(f"[BMWViewer] failed to start: {exc}")
