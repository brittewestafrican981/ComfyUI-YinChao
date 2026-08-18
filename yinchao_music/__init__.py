"""YinChao Music ComfyUI V3 package entrypoint."""


async def comfy_entrypoint():
    # Keep the pure API/client modules importable for offline tests and tools
    # that do not run inside ComfyUI. The V3 runtime imports the node module
    # only when it asks for the extension entrypoint.
    from .nodes import comfy_entrypoint as _entrypoint

    return await _entrypoint()


__all__ = ["comfy_entrypoint"]
