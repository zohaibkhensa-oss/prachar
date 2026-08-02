"""Domain Pack Architecture — plug-in domain packs for PRACHAR.

A Domain Pack defines the domain-specific behaviour for a customer segment
(Business, Creator, Restaurant, Clinic, etc.). The universal pipeline never
changes; only the Domain Pack changes.

Adding a new domain:
  1. Create a folder under domain_packs/<domain>/
  2. Implement a DomainPack subclass in pack.py
  3. Register it in register_all() below

Zero core modifications. No router changes, no dashboard changes, no pipeline
changes.
"""
from .base import (
    BaseDomainPack,
    DomainPack,
    DomainPackRegistry,
    get_registry,
    register_all,
)

__all__ = [
    "BaseDomainPack",
    "DomainPack",
    "DomainPackRegistry",
    "get_registry",
    "register_all",
]
