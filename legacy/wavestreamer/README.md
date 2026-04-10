# wavestreamer (deprecated)

**This package is retired. Please migrate to [`wavestreamer-sdk`](https://pypi.org/project/wavestreamer-sdk/).**

```bash
pip uninstall wavestreamer
pip install "wavestreamer-sdk[realtime]"
```

The `wavestreamer` package name was the original distribution. It has been superseded by `wavestreamer-sdk`, which includes the full CLI (`wavestreamer connect`, `wavestreamer status`), the WebSocket bridge, and all SDK features.

This tombstone release (999.0.0) depends on `wavestreamer-sdk` so that environments already pinned to `wavestreamer` continue to work, but please update your requirements files.
