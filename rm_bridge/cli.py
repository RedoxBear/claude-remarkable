"""CLI entry point — rm-bridge push / pull / list."""
import click

@click.group()
def main():
    """rm-bridge: Remarkable 2 document bridge (SSH + Connect)."""

@main.command()
@click.argument("file", type=click.Path(exists=True))
def push(file):
    """Push a PDF to the device."""
    raise NotImplementedError("Phase 1")

@main.command()
@click.argument("name")
def pull(name):
    """Pull annotated PDF by document name."""
    raise NotImplementedError("Phase 2")

@main.command()
def list():
    """List documents on the device."""
    raise NotImplementedError("Phase 1")
