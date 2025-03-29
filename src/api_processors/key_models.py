from dataclasses import dataclass
from typing import Optional


@dataclass
class OutlineKey:
    """
    Класс описания объекта ключа типа Outline
    """

    key_id: int
    name: str
    password: str
    port: int
    method: str
    access_url: str
    data_limit: int
    used_bytes: int

    @classmethod
    def from_key_json(cls, json_data: dict) -> "OutlineKey":
        return cls(
            key_id=int(json_data.get("id")),
            name=json_data.get("name"),
            password=json_data.get("password"),
            port=json_data.get("port"),
            method=json_data.get("method"),
            access_url=json_data.get("accessUrl"),
            data_limit=json_data.get("dataLimit", {}).get("bytes"),
            used_bytes=json_data.get("used_bytes"),
        )

    def __str__(self):
        return (
            f"OutlineKey(\n"
            f"  id={self.key_id},\n"
            f"  name={self.name},\n"
            f"  password={self.password},\n"
            f"  port={self.port},\n"
            f"  method={self.method},\n"
            f"  access_url={self.access_url},\n"
            f"  data_limit={self.data_limit},\n"
            f"  used_bytes={self.used_bytes}\n"
            f")"
        )


@dataclass
class VlessKey:
    """
    Класс описания объекта ключа типа Vless
    """

    key_id: str
    name: str
    email: str
    access_url: str
    used_bytes: int
    data_limit: int

    def __str__(self):
        return (
            f"VLESSKey(\n"
            f"  id={self.key_id},\n"
            f"  name={self.name},\n"
            f"  email={self.email},\n"
            f"  access_url={self.access_url},\n"
            f"  data_limit={self.data_limit},\n"
            f"  used_bytes={self.used_bytes}\n"
            f")"
        )
