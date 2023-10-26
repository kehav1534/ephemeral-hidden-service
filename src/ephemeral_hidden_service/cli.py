#!/usr/bin/python3
from base64 import b32encode
from time import sleep

import click
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from stem.control import Controller
from stem.response.add_onion import AddOnionResponse

DEFAULT_HIDDEN_SERVICE_PORT = 80


def generate_x25519_key_pair() -> (
    tuple[x25519.X25519PrivateKey, x25519.X25519PublicKey]
):
    # Generate a private key
    private_key: x25519.X25519PrivateKey = x25519.X25519PrivateKey.generate()

    # Extract the public key from the private key
    public_key: x25519.X25519PublicKey = private_key.public_key()

    return private_key, public_key


def encode_keys(
    private_key: x25519.X25519PrivateKey, public_key: x25519.X25519PublicKey
) -> tuple[str, str]:
    return tuple(  # type: ignore
        b32encode(keybytes).decode().rstrip("=")
        for keybytes in (
            private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            ),
            public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            ),
        )
    )


@click.command()
@click.option(
    "--local-port",
    "-lp",
    required=True,
    type=int,
    help="Local port to expose",
)
@click.option(
    "--hidden-service-port",
    "-hsp",
    required=False,
    default=DEFAULT_HIDDEN_SERVICE_PORT,
    type=int,
    help=f"Hidden service port, default {DEFAULT_HIDDEN_SERVICE_PORT}",
)
@click.option(
    "--controller-password",
    "-cp",
    required=False,
    type=str,
    help="Controller password, if any. Can be generated by `tor --hash-password ...`."
    "cf. https://wiki.archlinux.org/title/tor#Set_a_Tor_Control_password",
)
@click.option(
    "--public",
    default=False,
    type=bool,
    is_flag=True,
    help="Expose publicly, i.e. do not require client auth, cf. "
    "https://community.torproject.org/onion-services/advanced/client-auth/ ",
)
def start_ephemeral_service(
    local_port: int,
    hidden_service_port: int,
    public: bool,
    controller_password: str,
) -> None:
    with Controller.from_port() as controller:
        controller.authenticate(password=controller_password)

        if public:
            auth_config: dict[str, str] = {}
            encoded_private_key: str = ""
        else:
            # Generate the key pair
            private_key, public_key = generate_x25519_key_pair()
            encoded_private_key, encoded_public_key = encode_keys(
                private_key, public_key
            )
            auth_config: dict[str, str] = {"client_auth_v3": encoded_public_key}

        hidden_service_configuration: dict[str, str | bool | dict[int, int]] = {
            "ports": {hidden_service_port: local_port},
            "await_publication": True,
        } | auth_config

        response: AddOnionResponse = controller.create_ephemeral_hidden_service(
            **hidden_service_configuration  # type: ignore
        )

        assert response.service_id

        print("Ephemeral hidden service created")
        print(
            f"localhost:{local_port} is exposed at "
            f"{response.service_id}.onion:{hidden_service_port}"
        )

        if not public:
            print(f"Client authentication key: {encoded_private_key}")

        assert response.service_id in controller.list_ephemeral_hidden_services()
        try:
            print("Press Ctrl+C to interrupt...")

            while True:
                # Your code that you want to keep running until Ctrl+C is pressed
                sleep(1000)
        except KeyboardInterrupt:
            print("Ctrl+C pressed. Exiting...")

        controller.remove_ephemeral_hidden_service(response.service_id)
        assert response.service_id not in controller.list_ephemeral_hidden_services()
    print("Service terminated")


if __name__ == "__main__":
    start_ephemeral_service()
