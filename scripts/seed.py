from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from prachar_api.db import session_scope
from prachar_api.models import Actor, AuditEvent, Billing, Brand, Plan, Role, Tenant, User
from prachar_api.security import hash_password


async def main() -> None:
    from sqlalchemy import text

    # Phase 1: find or create tenant (tenants table has no RLS).
    async with session_scope() as session:
        res = await session.execute(select(Tenant).where(Tenant.name == "Demo Agency"))
        tenant = res.scalar_one_or_none()
        if tenant is not None:
            # Tenant exists — check if the demo user already exists
            res2 = await session.execute(
                text("SELECT id FROM users WHERE email = 'demo@prachar.app' LIMIT 1")
            )
            if res2.fetchone() is not None:
                print(f"Demo user already exists: demo@prachar.app (pw: prachar123)")
                return
            print(f"Demo tenant exists: {tenant.id} — creating demo user...")
        else:
            tenant = Tenant(name="Demo Agency", plan=Plan.growth, region="IN")
            session.add(tenant)
            await session.commit()
            print(f"Created demo tenant: {tenant.id}")

    # Phase 2: with RLS context set, create user/billing/brand/audit (only missing ones).
    async with session_scope(tenant_id=str(tenant.id)) as session:
        # Create user if missing
        from sqlalchemy import text as _text
        existing = await session.execute(
            _text("SELECT id FROM users WHERE email = 'demo@prachar.app' LIMIT 1")
        )
        if existing.fetchone() is None:
            user = User(
                tenant_id=tenant.id,
                email="demo@prachar.app",
                role=Role.owner,
                pw_hash=hash_password("prachar123"),
            )
            session.add(user)
            print("  + Created demo user: demo@prachar.app")
        else:
            print("  = User already exists")

        # Create billing if missing
        existing = await session.execute(
            _text("SELECT id FROM billing WHERE tenant_id = :tid"), {"tid": str(tenant.id)}
        )
        if existing.fetchone() is None:
            billing = Billing(tenant_id=tenant.id, provider="stripe", ai_budget_month=1000)
            session.add(billing)
            print("  + Created billing")

        # Create brand if missing
        existing = await session.execute(
            _text("SELECT id FROM brands WHERE tenant_id = :tid AND name = 'Acme Coffee Co.'"),
            {"tid": str(tenant.id)},
        )
        if existing.fetchone() is None:
            brand = Brand(
                tenant_id=tenant.id,
                name="Acme Coffee Co.",
                website="https://acmecoffee.example",
                category="food & beverage",
                locales=["en-IN", "hi-IN"],
                tone={"voice": "warm", "register": "casual"},
                visibility_score=42.0,
            )
            session.add(brand)
            print("  + Created brand: Acme Coffee Co.")

        await session.flush()
        session.add(
            AuditEvent(
                tenant_id=tenant.id,
                actor=Actor.system,
                action="seed",
                entity_type="tenant",
                entity_id=str(tenant.id),
                payload={"demo_user": "demo@prachar.app", "brand": "Acme Coffee Co."},
            )
        )
        await session.commit()
        print(f"\n✅ Demo credentials ready:")
        print(f"   Email: demo@prachar.app")
        print(f"   Password: prachar123")


if __name__ == "__main__":
    asyncio.run(main())
