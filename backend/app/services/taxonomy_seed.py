import json

from sqlalchemy import select

from app.models.profile import Goal, Interest, Region


async def seed_taxonomy(session, path):
    data = json.loads(path.read_text())
    for key, model in (("goals", Goal), ("interests", Interest), ("regions", Region)):
        for values in data[key]:
            item = await session.scalar(select(model).where(model.code == values["code"]))
            if item is None:
                session.add(model(**values))
            else:
                for field, value in values.items():
                    setattr(item, field, value)
    await session.commit()
