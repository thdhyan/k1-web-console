# k1-web-console

Fleet dashboard and camera tools; one web shell, plugin pages over HTTP/WS.

| | |
|---|---|
| Layer | **L3**: Apps (processes you start) |
| May import | nothing |
| Files / LOC | 8 files · 554 lines (py, sh, cpp) |
| Part of | [k1-workspace](https://github.com/thdhyan/k1-workspace) (architecture and layering rules live there) |

## Install

Not an installable library: clone it and run the scripts in place.
```bash
git clone https://github.com/thdhyan/k1-web-console
```

## Layout

```
docker/  (1 files)
  k1m_ui.py
docs/  (4 files)
  velocity_grid/  (4 files)
pyproject.toml
tools/  (3 files)
  fleet_dashboard/  (1 files)
  k1_camera/  (2 files)
```

## Dependencies

- Declared sibling libraries: none (see `pyproject.toml`, `[tool.uv.sources]`).
- PyPI: numpy, opencv-python, requests, websockets.
- Provided by the environment (ROS 2, Isaac, mjlab, robot SDK) or unresolved: `rclpy`, `sensor_msgs`, `streamlit`.

## Hard-coded paths into other repos

None.

## Origin

Extracted from `booster_ws` (branch `dev/push-training-wip`, working tree of 2026-11-03) by
`tools/build_workspace.py` in k1-workspace. Old path to new path for every file: [`docs/migration_map.tsv`](https://github.com/thdhyan/k1-workspace/blob/main/docs/migration_map.tsv) (filter on `k1-web-console`).
History was not carried over: the working tree was copied as is, including previously untracked files.
