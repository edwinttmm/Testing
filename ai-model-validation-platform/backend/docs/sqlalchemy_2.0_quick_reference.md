# SQLAlchemy 2.0 Quick Reference Card

## Essential Imports
```python
from sqlalchemy import select, delete, update, func
from sqlalchemy.orm import Session
```

## Common Query Patterns

### Get Single Object

#### Old (SQLAlchemy 1.x)
```python
user = session.query(User).filter(User.id == 1).first()
```

#### New (SQLAlchemy 2.0)
```python
user = session.execute(select(User).where(User.id == 1)).scalar_one_or_none()
```

---

### Get All Objects

#### Old
```python
users = session.query(User).filter(User.active == True).all()
```

#### New
```python
users = session.execute(select(User).where(User.active == True)).scalars().all()
```

---

### Count Records

#### Old
```python
count = session.query(User).filter(User.role == 'admin').count()
```

#### New
```python
count = session.execute(
    select(func.count()).select_from(User).where(User.role == 'admin')
).scalar()
```

---

### Filter By

#### Old
```python
user = session.query(User).filter_by(username='john').first()
```

#### New
```python
user = session.execute(
    select(User).filter_by(username='john')
).scalar_one_or_none()
```

---

### Delete Records

#### Old
```python
session.query(User).filter(User.active == False).delete()
```

#### New
```python
session.execute(delete(User).where(User.active == False))
```

---

### Join Tables

#### Old
```python
result = session.query(User).join(Profile).first()
```

#### New
```python
result = session.execute(select(User).join(Profile)).scalar_one_or_none()
```

---

### Like Pattern Matching

#### Old
```python
users = session.query(User).filter(User.email.like('%@example.com')).all()
```

#### New
```python
users = session.execute(
    select(User).where(User.email.like('%@example.com'))
).scalars().all()
```

---

### Limit Results

#### Old
```python
users = session.query(User).limit(10).all()
```

#### New
```python
users = session.execute(select(User).limit(10)).scalars().all()
```

---

### Pessimistic Locking

#### Old
```python
user = session.query(User).filter(User.id == 1).with_for_update().first()
```

#### New
```python
user = session.execute(
    select(User).where(User.id == 1).with_for_update()
).scalar_one_or_none()
```

---

### Aggregate Functions

#### Old
```python
avg_age = session.query(func.avg(User.age)).scalar()
```

#### New
```python
avg_age = session.execute(select(func.avg(User.age))).scalar()
```

---

## Result Methods

| Method | Returns | Use Case |
|--------|---------|----------|
| `.scalar()` | Single value or None | For aggregate functions (count, sum, avg) |
| `.scalar_one()` | Single value | When you expect exactly one result |
| `.scalar_one_or_none()` | Single value or None | When you expect 0 or 1 result |
| `.scalars()` | Scalars iterator | To get scalar values (objects) |
| `.scalars().all()` | List of objects | To get all matching records |
| `.scalars().first()` | First object or None | To get first result |

## Common Mistakes to Avoid

### ❌ Mistake 1: Forgetting .scalars()
```python
# Wrong - returns Row objects
users = session.execute(select(User)).all()

# Correct - returns User objects
users = session.execute(select(User)).scalars().all()
```

### ❌ Mistake 2: Using .first() directly
```python
# Wrong - AttributeError
user = session.execute(select(User)).first()

# Correct
user = session.execute(select(User)).scalars().first()
```

### ❌ Mistake 3: Wrong result method for count
```python
# Wrong - returns Result object
count = session.execute(select(func.count()).select_from(User))

# Correct - returns integer
count = session.execute(select(func.count()).select_from(User)).scalar()
```

### ❌ Mistake 4: Using .filter() instead of .where()
```python
# Old style (deprecated)
stmt = select(User).filter(User.active == True)

# New style (preferred)
stmt = select(User).where(User.active == True)
```

## Complex Examples

### Multiple Filters
```python
# Old
users = session.query(User).filter(
    User.age >= 18,
    User.active == True,
    User.role.in_(['admin', 'user'])
).all()

# New
users = session.execute(
    select(User).where(
        User.age >= 18,
        User.active == True,
        User.role.in_(['admin', 'user'])
    )
).scalars().all()
```

### Join with Filter
```python
# Old
results = session.query(User).join(Profile).filter(
    Profile.verified == True
).all()

# New
results = session.execute(
    select(User).join(Profile).where(
        Profile.verified == True
    )
).scalars().all()
```

### Count Distinct
```python
# Old
count = session.query(User).join(Order).distinct().count()

# New
count = session.execute(
    select(func.count(func.distinct(User.id)))
    .select_from(User)
    .join(Order)
).scalar()
```

## Migration Checklist

- [ ] Add required imports: `select`, `delete`, `update`, `func`
- [ ] Replace `session.query()` with `session.execute(select())`
- [ ] Replace `.filter()` with `.where()`
- [ ] Replace `.first()` with `.scalar_one_or_none()`
- [ ] Replace `.all()` with `.scalars().all()`
- [ ] Replace `.count()` with `func.count()` and `.scalar()`
- [ ] Update delete operations to use `delete()`
- [ ] Test thoroughly after migration

## Additional Resources

- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Migration Guide](https://docs.sqlalchemy.org/en/20/changelog/migration_20.html)
- [ORM Query Tutorial](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html)
