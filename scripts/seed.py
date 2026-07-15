from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from prachar_api.db import session_scope
from prachar_api.models import Actor, AuditEvent, Billing, Brand, Plan, Role, Tenant, User
from prachar_api.security import hash_password


async def main() -> None:
    from sqlalchemy import text

    # Phase 1: create tenant (tenants table has no RLS).
    async with session_scope() as session:
        res = await session.execute(select(Tenant).where(Tenant.name == "Demo Agency"))
        tenant = res.scalar_one_or_none()
        if tenant is not None:
            print(f"Demo tenant already exists: {tenant.id}")
            return
        tenant = Tenant(name="Demo Agency", plan=Plan.growth, region="IN")
        session.add(tenant)
        await session.commit()

    # Phase 2: with RLS context set, create user/billing/brand/audit.
    async with session_scope(tenant_id=str(tenant.id)) as session:
        user = User(
            tenant_id=tenant.id,
            email="demo@prachar.app",
            role=Role.owner,
            pw_hash=hash_password("prachar123"),
        )
        session.add(user)
        billing = Billing(tenant_id=tenant.id, provider="stripe", ai_budget_month=1000)
        session.add(billing)
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
        await session.flush()
        session.add(
            AuditEvent(
                tenant_id=tenant.id,
                actor=Actor.system,
                action="seed",
                entity_type="tenant",
                entity_id=str(tenant.id),
                payload={"demo_user": user.email, "brand": brand.name},
            )
        )
        await session.commit()
        print(f"Seeded tenant {tenant.id} user demo@prachar.app (pw: prachar123) brand {brand.name}")


if __name__ == "__main__":
    asyncio.run(main())
