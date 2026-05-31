"""
SQLAdmin panel — /admin
Protected by username + password from settings.
"""

from datetime import UTC, datetime, timedelta

from sqladmin import Admin, ModelView, action
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import RedirectResponse

from core.logging import get_logger
from core.settings import settings
from db.database import AsyncSessionLocal, engine
from db.models import (
    DailyHoroscope,
    Interpretation,
    MacCard,
    MacReading,
    NatalChart,
    Purchase,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    TarotCard,
    TarotPositionMeaning,
    TarotReading,
    User,
)

log = get_logger(__name__)


# ── Auth ──────────────────────────────────────────────────────────────────────
class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        if (
            form.get("username") == settings.ADMIN_USERNAME
            and form.get("password") == settings.ADMIN_PASSWORD
        ):
            request.session["admin"] = True
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return request.session.get("admin") is True


# ── Views ─────────────────────────────────────────────────────────────────────
class UserAdmin(ModelView, model=User):
    name = "Пользователь"
    name_plural = "Пользователи"
    icon = "fa-solid fa-users"
    column_list = [
        User.id, User.tg_first_name, User.tg_username,
        User.sun_sign, User.birth_city, User.tg_is_premium, User.created_at,
    ]
    column_searchable_list = [User.tg_first_name, User.tg_username]
    column_sortable_list = [User.created_at, User.sun_sign]
    # Show subscriptions + purchases inline on the detail page so an
    # operator can immediately see whether the user has active Premium
    # (status=active + expires_at in the future) and which one-off
    # products they bought.
    column_details_exclude_list = [User.natal_chart, User.tarot_readings]
    can_delete = True
    can_edit = True
    can_create = False

    @action(
        name="grant_premium_year",
        label="Выдать Premium на 1 год",
        confirmation_message="Выдать Premium на 365 дней выбранным пользователям? "
                             "Если активная подписка уже есть — продлим её на год.",
        add_in_detail=True,
        add_in_list=True,
    )
    async def grant_premium_year(self, request: Request) -> RedirectResponse:
        pks = _parse_pks(request)
        if not pks:
            return _redirect_back(request)

        now = datetime.now(UTC)
        extension = timedelta(days=365)

        async with AsyncSessionLocal() as session:
            for uid in pks:
                # If there's an active sub that hasn't expired — extend it.
                result = await session.execute(
                    select(Subscription)
                    .where(
                        Subscription.user_id == uid,
                        Subscription.status == SubscriptionStatus.ACTIVE,
                    )
                    .order_by(Subscription.expires_at.desc())
                    .limit(1)
                )
                sub = result.scalar_one_or_none()
                if sub and sub.expires_at > now:
                    sub.expires_at = sub.expires_at + extension
                    log.info("admin.premium.extended", user_id=uid,
                             new_expires=sub.expires_at.isoformat())
                else:
                    session.add(Subscription(
                        user_id=uid,
                        plan=SubscriptionPlan.PREMIUM_YEAR,
                        status=SubscriptionStatus.ACTIVE,
                        stars_paid=0,
                        tg_payment_charge_id=f"admin-grant-{uid}-{int(now.timestamp())}",
                        starts_at=now,
                        expires_at=now + extension,
                        is_trial=True,
                        trial_reason="admin_grant",
                    ))
                    log.info("admin.premium.granted", user_id=uid, days=365)
            await session.commit()
        return _redirect_back(request)

    @action(
        name="revoke_premium",
        label="Отозвать Premium",
        confirmation_message="Отозвать все активные подписки у выбранных пользователей?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def revoke_premium(self, request: Request) -> RedirectResponse:
        pks = _parse_pks(request)
        if not pks:
            return _redirect_back(request)

        async with AsyncSessionLocal() as session:
            for uid in pks:
                result = await session.execute(
                    select(Subscription).where(
                        Subscription.user_id == uid,
                        Subscription.status == SubscriptionStatus.ACTIVE,
                    )
                )
                for sub in result.scalars():
                    sub.status = SubscriptionStatus.CANCELLED
                    log.info("admin.premium.revoked",
                             user_id=uid, subscription_id=sub.id)
            await session.commit()
        return _redirect_back(request)


def _parse_pks(request: Request) -> list[int]:
    raw = request.query_params.get("pks", "")
    return [int(p) for p in raw.split(",") if p.strip().isdigit()]


def _redirect_back(request: Request) -> RedirectResponse:
    """SQLAdmin actions return to the page they were called from."""
    referer = request.headers.get("referer")
    if referer:
        return RedirectResponse(referer, status_code=302)
    return RedirectResponse(request.url_for("admin:list", identity="user"),
                            status_code=302)


class NatalChartAdmin(ModelView, model=NatalChart):
    name = "Натальная карта"
    name_plural = "Натальные карты"
    icon = "fa-solid fa-circle-nodes"
    column_list = [NatalChart.id, NatalChart.user_id, NatalChart.sun_sign, NatalChart.moon_sign, NatalChart.ascendant_sign, NatalChart.created_at]
    column_sortable_list = [NatalChart.created_at]
    can_create = False
    can_edit = False


class InterpretationAdmin(ModelView, model=Interpretation):
    name = "Интерпретация"
    name_plural = "Интерпретации"
    icon = "fa-solid fa-book-open"
    column_list = [Interpretation.id, Interpretation.planet, Interpretation.sign, Interpretation.house, Interpretation.aspect]
    column_searchable_list = [Interpretation.planet, Interpretation.sign]
    column_sortable_list = [Interpretation.planet, Interpretation.sign]
    can_create = True
    can_edit = True
    can_delete = True
    page_size = 50


class DailyHoroscopeAdmin(ModelView, model=DailyHoroscope):
    name = "Гороскоп"
    name_plural = "Гороскопы"
    icon = "fa-solid fa-star"
    column_list = [DailyHoroscope.id, DailyHoroscope.sign, DailyHoroscope.date, DailyHoroscope.period, DailyHoroscope.created_at]
    column_searchable_list = [DailyHoroscope.sign]
    column_sortable_list = [DailyHoroscope.date, DailyHoroscope.sign]
    can_create = True
    can_edit = True
    can_delete = True
    page_size = 50


class TarotCardAdmin(ModelView, model=TarotCard):
    name = "Карта Таро"
    name_plural = "Карты Таро"
    icon = "fa-solid fa-cards-blank"
    column_list = [TarotCard.id, TarotCard.emoji, TarotCard.name_ru, TarotCard.arcana, TarotCard.number]
    column_searchable_list = [TarotCard.name_ru, TarotCard.name_en]
    column_sortable_list = [TarotCard.arcana, TarotCard.number]
    can_create = True
    can_edit = True
    can_delete = True
    page_size = 100


class TarotPositionMeaningAdmin(ModelView, model=TarotPositionMeaning):
    name = "Позиция расклада"
    name_plural = "Позиции расклада"
    icon = "fa-solid fa-layer-group"
    column_list = [TarotPositionMeaning.id, TarotPositionMeaning.card_id, TarotPositionMeaning.spread_type, TarotPositionMeaning.position, TarotPositionMeaning.position_name_ru]
    column_searchable_list = [TarotPositionMeaning.spread_type]
    column_sortable_list = [TarotPositionMeaning.spread_type, TarotPositionMeaning.position]
    can_create = True
    can_edit = True
    can_delete = True
    page_size = 50


class TarotReadingAdmin(ModelView, model=TarotReading):
    name = "Расклад"
    name_plural = "Расклады"
    icon = "fa-solid fa-rectangle-history"
    column_list = [TarotReading.id, TarotReading.user_id, TarotReading.spread_type, TarotReading.created_at]
    column_sortable_list = [TarotReading.created_at]
    can_create = False
    can_edit = False
    can_delete = True
    page_size = 50


class SubscriptionAdmin(ModelView, model=Subscription):
    name = "Подписка"
    name_plural = "Подписки"
    icon = "fa-solid fa-crown"
    column_list = [Subscription.id, Subscription.user_id, Subscription.plan, Subscription.status, Subscription.expires_at]
    column_sortable_list = [Subscription.created_at, Subscription.expires_at]
    can_create = True
    can_edit = True
    can_delete = True


class MacCardAdmin(ModelView, model=MacCard):
    name = "МАК-карта"
    name_plural = "МАК-карты"
    icon = "fa-solid fa-eye"
    column_list = [MacCard.id, MacCard.name_ru, MacCard.category, MacCard.emoji]
    column_searchable_list = [MacCard.name_ru]
    column_sortable_list = [MacCard.category]
    can_create = True
    can_edit = True
    can_delete = True
    page_size = 60


class MacReadingAdmin(ModelView, model=MacReading):
    name = "МАК-расклад"
    name_plural = "МАК-расклады"
    icon = "fa-solid fa-mirror"
    column_list = [MacReading.id, MacReading.user_id, MacReading.card_id, MacReading.created_at]
    column_sortable_list = [MacReading.created_at]
    can_create = False
    can_edit = False
    can_delete = True
    page_size = 50


class PurchaseAdmin(ModelView, model=Purchase):
    name = "Покупка"
    name_plural = "Покупки"
    icon = "fa-solid fa-receipt"
    column_list = [Purchase.id, Purchase.user_id, Purchase.product_id, Purchase.status, Purchase.stars_amount, Purchase.created_at]
    column_sortable_list = [Purchase.created_at]
    can_create = False
    can_edit = True
    can_delete = False


# ── Factory ───────────────────────────────────────────────────────────────────
def create_admin(app) -> Admin:
    authentication_backend = AdminAuth(secret_key=settings.APP_SECRET_KEY)
    admin = Admin(
        app,
        engine=engine,
        authentication_backend=authentication_backend,
        title="Astro TMA — Admin",
        base_url="/admin",
    )
    for view in [
        UserAdmin, NatalChartAdmin, InterpretationAdmin,
        DailyHoroscopeAdmin, TarotCardAdmin, TarotPositionMeaningAdmin,
        TarotReadingAdmin, MacCardAdmin, MacReadingAdmin,
        SubscriptionAdmin, PurchaseAdmin,
    ]:
        admin.add_view(view)
    return admin
