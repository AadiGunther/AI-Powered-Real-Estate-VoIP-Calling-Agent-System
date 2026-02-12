"""Seed database with sample solar panel products."""

import asyncio
import json

from sqlalchemy import select

from app.database import async_session_maker, init_db
from app.models.product import Product, ProductType
from app.models.user import User, UserRole
from app.utils.security import get_password_hash


SAMPLE_PRODUCTS = [
    {
        "name": "Ujjwal Mono PERC 440W",
        "model_number": "UJ-MONO-440",
        "type": ProductType.MONOCRYSTALLINE.value,
        "wattage": 440,
        "efficiency": 20.2,
        "length_mm": 1900,
        "width_mm": 1134,
        "thickness_mm": 35,
        "weight_kg": 23.5,
        "price_inr": 11500,
        "warranty_years": 25,
        "manufacturer": "Ujjwal Energies",
        "manufacturer_country": "India",
        "description": "440W mono PERC module ideal for residential rooftop systems.",
        "technical_specifications": "Voc: 49.5V; Isc: 11.2A; Operating temp: -40°C to 85°C;",
        "images": json.dumps(["/static/uj_mono_440_front.jpg"]),
    },
    {
        "name": "SunPower Maxeon 3 400W",
        "model_number": "SP-MAX3-400",
        "type": ProductType.MONOCRYSTALLINE.value,
        "wattage": 400,
        "efficiency": 22.6,
        "length_mm": 1690,
        "width_mm": 1046,
        "thickness_mm": 40,
        "weight_kg": 19.0,
        "price_inr": 23500,
        "warranty_years": 25,
        "manufacturer": "SunPower",
        "manufacturer_country": "USA",
        "description": "Premium high-efficiency module for space-constrained rooftops.",
        "technical_specifications": "N-type cells; degradation <0.25%/year; PID-free design;",
        "images": json.dumps(["/static/sp_max3_400.jpg"]),
    },
    {
        "name": "Canadian Solar HiKu 545W",
        "model_number": "CS-HIKU-545",
        "type": ProductType.MONOCRYSTALLINE.value,
        "wattage": 545,
        "efficiency": 21.3,
        "length_mm": 2256,
        "width_mm": 1134,
        "thickness_mm": 35,
        "weight_kg": 28.5,
        "price_inr": 18500,
        "warranty_years": 25,
        "manufacturer": "Canadian Solar",
        "manufacturer_country": "Canada",
        "description": "Utility-scale 545W module suitable for ground-mount plants.",
        "technical_specifications": "Half-cut cells; 1500V system voltage; bifacial-ready frame;",
        "images": json.dumps(["/static/cs_hiku_545.jpg"]),
    },
    {
        "name": "Adani Solar 335W Poly",
        "model_number": "AD-POLY-335",
        "type": ProductType.POLYCRYSTALLINE.value,
        "wattage": 335,
        "efficiency": 16.9,
        "length_mm": 1960,
        "width_mm": 992,
        "thickness_mm": 35,
        "weight_kg": 22.0,
        "price_inr": 7800,
        "warranty_years": 10,
        "manufacturer": "Adani Solar",
        "manufacturer_country": "India",
        "description": "Cost-effective polycrystalline module for budget-sensitive projects.",
        "technical_specifications": "Positive power tolerance 0/+5W; wind load 2400 Pa;",
        "images": json.dumps(["/static/ad_poly_335.jpg"]),
    },
    {
        "name": "Vikram Eldora 370W Mono",
        "model_number": "VK-ELD-370",
        "type": ProductType.MONOCRYSTALLINE.value,
        "wattage": 370,
        "efficiency": 19.2,
        "length_mm": 1765,
        "width_mm": 1048,
        "thickness_mm": 35,
        "weight_kg": 19.5,
        "price_inr": 9800,
        "warranty_years": 25,
        "manufacturer": "Vikram Solar",
        "manufacturer_country": "India",
        "description": "Mono PERC panel optimized for Indian climatic conditions.",
        "technical_specifications": "Salt mist resistant; ammonia resistant; IP68 junction box;",
        "images": json.dumps(["/static/vk_eld_370.jpg"]),
    },
    {
        "name": "RenewSys Deserv Poly 320W",
        "model_number": "RS-DES-320",
        "type": ProductType.POLYCRYSTALLINE.value,
        "wattage": 320,
        "efficiency": 16.4,
        "length_mm": 1956,
        "width_mm": 992,
        "thickness_mm": 35,
        "weight_kg": 21.0,
        "price_inr": 7200,
        "warranty_years": 10,
        "manufacturer": "RenewSys",
        "manufacturer_country": "India",
        "description": "Polycrystalline module for small to mid-size rooftop projects.",
        "technical_specifications": "Class II module; 5400 Pa snow load; low LID cells;",
        "images": json.dumps(["/static/rs_des_320.jpg"]),
    },
    {
        "name": "First Solar Series 6 450W",
        "model_number": "FS-S6-450",
        "type": ProductType.THIN_FILM.value,
        "wattage": 450,
        "efficiency": 18.0,
        "length_mm": 2030,
        "width_mm": 1240,
        "thickness_mm": 35,
        "weight_kg": 32.0,
        "price_inr": 21000,
        "warranty_years": 30,
        "manufacturer": "First Solar",
        "manufacturer_country": "USA",
        "description": "Cadmium telluride thin-film module for utility-scale plants.",
        "technical_specifications": "Lower temperature coefficient; better diffuse light response;",
        "images": json.dumps(["/static/fs_s6_450.jpg"]),
    },
    {
        "name": "JA Solar DeepBlue 3.0 540W",
        "model_number": "JA-DB3-540",
        "type": ProductType.MONOCRYSTALLINE.value,
        "wattage": 540,
        "efficiency": 21.0,
        "length_mm": 2279,
        "width_mm": 1134,
        "thickness_mm": 35,
        "weight_kg": 28.2,
        "price_inr": 17900,
        "warranty_years": 25,
        "manufacturer": "JA Solar",
        "manufacturer_country": "China",
        "description": "High-power mono PERC module with M10 wafers.",
        "technical_specifications": "Multi-busbar; anti-PID; enhanced low-light performance;",
        "images": json.dumps(["/static/ja_db3_540.jpg"]),
    },
    {
        "name": "Trina Vertex S 415W",
        "model_number": "TR-VERT-415",
        "type": ProductType.MONOCRYSTALLINE.value,
        "wattage": 415,
        "efficiency": 21.3,
        "length_mm": 1722,
        "width_mm": 1134,
        "thickness_mm": 30,
        "weight_kg": 21.0,
        "price_inr": 13200,
        "warranty_years": 25,
        "manufacturer": "Trina Solar",
        "manufacturer_country": "China",
        "description": "Compact high-power module ideal for residential roofs.",
        "technical_specifications": "Dual-glass option; improved mechanical loading; 1500V system;",
        "images": json.dumps(["/static/tr_vert_415.jpg"]),
    },
    {
        "name": "Waaree Aditya 540W Bifacial",
        "model_number": "WA-ADI-540B",
        "type": ProductType.MONOCRYSTALLINE.value,
        "wattage": 540,
        "efficiency": 21.2,
        "length_mm": 2278,
        "width_mm": 1134,
        "thickness_mm": 35,
        "weight_kg": 30.0,
        "price_inr": 18900,
        "warranty_years": 30,
        "manufacturer": "Waaree Energies",
        "manufacturer_country": "India",
        "description": "Bifacial mono PERC module for trackers and ground-mount plants.",
        "technical_specifications": "Glass-glass construction; bifacial gain up to 25%;",
        "images": json.dumps(["/static/wa_adi_540b.jpg"]),
    },
]


async def seed_products():
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.role == UserRole.ADMIN.value))
        admin = result.scalar_one_or_none()

        if not admin:
            admin = User(
                email="admin@solardemo.com",
                full_name="Solar Admin",
                hashed_password=get_password_hash("admin123"),
                role=UserRole.ADMIN.value,
                is_active=True,
            )
            db.add(admin)
            await db.flush()

        result = await db.execute(select(Product))
        existing = result.scalars().all()

        if existing:
            print(f"Database already has {len(existing)} products. Skipping seed.")
            return

        for data in SAMPLE_PRODUCTS:
            product = Product(
                **data,
                is_active=True,
            )
            db.add(product)

        await db.commit()
        print(f"✅ Successfully added {len(SAMPLE_PRODUCTS)} sample products.")


async def main():
    await init_db()
    await seed_products()


if __name__ == "__main__":
    asyncio.run(main())

