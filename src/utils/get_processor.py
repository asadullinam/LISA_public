from initialization.outline_processor_init import async_outline_processor
from initialization.vless_processor_init import vless_processor


async def get_processor(vpn_type: str):
    vpn_type = vpn_type.lower()
    processors = {"outline": async_outline_processor, "vless": vless_processor}
    return processors.get(vpn_type.lower())
