"""Root custom-node entrypoint for ComfyUI V3 discovery."""


async def comfy_entrypoint():
    # ComfyUI loads the repository root as the custom-node package. Keep the
    # implementation in the named package so it remains easy to test and
    # package, while exposing the required V3 entrypoint at the install root.
    from .yinchao_music import comfy_entrypoint as _entrypoint

    return await _entrypoint()


__all__ = ["comfy_entrypoint"]
