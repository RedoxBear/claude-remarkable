"""CLI entry point — rm-bridge push / pull / list / register."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from . import ReMarkable


def _ssh_rm(host: str, key: str | None, password: str | None) -> ReMarkable:
    rm = ReMarkable.over_ssh(host=host, key_path=key, password=password)
    rm.connect()
    return rm


def _connect_rm(token_path: str | None) -> ReMarkable:
    rm = ReMarkable.from_connect(Path(token_path) if token_path else None)
    rm.connect()
    return rm


@click.group()
@click.version_option()
def main() -> None:
    """rm-bridge: Remarkable 2 document bridge (SSH + Connect)."""


# ------------------------------------------------------------------
# SSH commands
# ------------------------------------------------------------------

@main.group()
def ssh() -> None:
    """SSH transport commands (direct device access)."""


@ssh.command("list")
@click.option("--host", default="10.11.99.1", show_default=True, help="Device IP address.")
@click.option("--key", default=None, help="Path to SSH private key.")
@click.option("--password", default=None, help="SSH password (prefer key auth).")
def ssh_list(host: str, key: str | None, password: str | None) -> None:
    """List documents on the device."""
    with _ssh_rm(host, key, password) as rm:
        docs = rm.list_documents()
    if not docs:
        click.echo("No documents found.")
        return
    for doc in docs:
        click.echo(f"{doc.uuid}  {doc.title!r}  ({doc.page_count}p, {doc.file_type})")


@ssh.command("push")
@click.argument("file", type=click.Path(exists=True))
@click.option("--title", default=None, help="Document title (defaults to filename).")
@click.option("--host", default="10.11.99.1", show_default=True)
@click.option("--key", default=None)
@click.option("--password", default=None)
def ssh_push(file: str, title: str | None, host: str, key: str | None, password: str | None) -> None:
    """Push a PDF to the device."""
    with _ssh_rm(host, key, password) as rm:
        doc = rm.push_pdf(file, title=title)
    click.echo(f"Pushed: {doc.title!r} → {doc.uuid}")


@ssh.command("pull")
@click.argument("uuid")
@click.option("--out", default=None, help="Output file path (defaults to <uuid>.pdf).")
@click.option("--host", default="10.11.99.1", show_default=True)
@click.option("--key", default=None)
@click.option("--password", default=None)
def ssh_pull(uuid: str, out: str | None, host: str, key: str | None, password: str | None) -> None:
    """Pull a document PDF by UUID."""
    with _ssh_rm(host, key, password) as rm:
        data = rm.pull_document(uuid)
    dest = Path(out or f"{uuid}.pdf")
    dest.write_bytes(data)
    click.echo(f"Saved {len(data):,} bytes → {dest}")


@ssh.command("render")
@click.argument("uuid")
@click.option("--out", default=None, help="Output file path (defaults to <uuid>-annotated.pdf).")
@click.option("--host", default="10.11.99.1", show_default=True)
@click.option("--key", default=None)
@click.option("--password", default=None)
def ssh_render(uuid: str, out: str | None, host: str, key: str | None, password: str | None) -> None:
    """Pull a document and render its annotations onto the PDF."""
    with _ssh_rm(host, key, password) as rm:
        data = rm.render_document(uuid)
    dest = Path(out or f"{uuid}-annotated.pdf")
    dest.write_bytes(data)
    click.echo(f"Saved annotated PDF ({len(data):,} bytes) → {dest}")


@ssh.command("info")
@click.option("--host", default="10.11.99.1", show_default=True)
@click.option("--key", default=None)
@click.option("--password", default=None)
def ssh_info(host: str, key: str | None, password: str | None) -> None:
    """Show device serial and firmware version."""
    with _ssh_rm(host, key, password) as rm:
        info = rm.device_info()
    click.echo(json.dumps(info, indent=2))


# ------------------------------------------------------------------
# Connect commands
# ------------------------------------------------------------------

@main.group()
def connect() -> None:
    """Remarkable Connect (cloud) transport commands."""


@connect.command("register")
@click.argument("code")
@click.option("--token-path", default=None, help="Custom token storage path.")
def connect_register(code: str, token_path: str | None) -> None:
    """Register with a one-time code from my.remarkable.com/device/desktop/connect."""
    rm = ReMarkable.from_connect(Path(token_path) if token_path else None)
    rm.register(code)
    click.echo("Device registered. Run 'rm-bridge connect list' to verify.")


@connect.command("list")
@click.option("--token-path", default=None)
def connect_list(token_path: str | None) -> None:
    """List documents in the cloud account."""
    with _connect_rm(token_path) as rm:
        docs = rm.list_documents()
    if not docs:
        click.echo("No documents found.")
        return
    for doc in docs:
        click.echo(f"{doc.uuid}  {doc.title!r}  ({doc.page_count}p, {doc.file_type})")


@connect.command("push")
@click.argument("file", type=click.Path(exists=True))
@click.option("--title", default=None)
@click.option("--token-path", default=None)
def connect_push(file: str, title: str | None, token_path: str | None) -> None:
    """Push a PDF to the cloud."""
    with _connect_rm(token_path) as rm:
        doc = rm.push_pdf(file, title=title)
    click.echo(f"Pushed: {doc.title!r} → {doc.uuid}")


@connect.command("pull")
@click.argument("uuid")
@click.option("--out", default=None)
@click.option("--token-path", default=None)
def connect_pull(uuid: str, out: str | None, token_path: str | None) -> None:
    """Pull a document PDF from the cloud by UUID."""
    with _connect_rm(token_path) as rm:
        data = rm.pull_document(uuid)
    dest = Path(out or f"{uuid}.pdf")
    dest.write_bytes(data)
    click.echo(f"Saved {len(data):,} bytes → {dest}")
