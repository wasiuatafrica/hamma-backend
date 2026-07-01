from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from portfolio.models import CompanyProfile, Stock

EMPTY_OVERVIEW: dict[str, Any] = {
    "marketcap": 0,
    "CompanyName": "",
    "Sector": "",
    "SubSector": "",
    "dividend": 0,
    "MarketClassification": "",
    "DateOfIncorporation": None,
    "Website": "",
    "NatureofBusiness": "",
    "CompanyAddress": "",
    "Telephone": "",
    "HIGH52WK_PRICE": None,
    "LOW52WK_PRICE": None,
    "BoardOfDirectors": "",
    "Email": "",
}


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value)[:10], fmt).date()
        except ValueError:
            continue
    return None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _truncate(value: Any, max_length: int) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) <= max_length:
        return text
    return text[:max_length]


def _profile_field_values(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_name": _truncate(data.get("CompanyName", ""), 255),
        "sub_sector": _truncate(data.get("SubSector", ""), 100),
        "market_classification": _truncate(data.get("MarketClassification", ""), 100),
        "date_of_incorporation": _parse_date(data.get("DateOfIncorporation")),
        "website": _truncate(data.get("Website", ""), 500),
        "nature_of_business": data.get("NatureofBusiness", "") or "",
        "company_address": data.get("CompanyAddress", "") or "",
        "telephone": data.get("Telephone", "") or "",
        "email": _truncate(data.get("Email", ""), 254),
        "board_of_directors": data.get("BoardOfDirectors", "") or "",
        "shares_outstanding": _to_decimal(data.get("SharesOutstanding")),
        "prev_close": _to_decimal(data.get("PrevClose")),
        "dividend": _to_decimal(data.get("dividend")),
        "high_52wk_price": _to_decimal(data.get("HIGH52WK_PRICE")),
        "low_52wk_price": _to_decimal(data.get("LOW52WK_PRICE")),
        "raw_ngx_data": data,
    }


def _sync_stock_from_ngx(stock: Stock, data: dict[str, Any]) -> None:
    update_fields: list[str] = []
    company_name = data.get("CompanyName")
    if company_name:
        stock.company = _truncate(company_name, 200)
        update_fields.append("company")
    sector = data.get("Sector")
    if sector:
        stock.sector = _truncate(sector, 50)
        update_fields.append("sector")
    incorporation_date = _parse_date(data.get("DateOfIncorporation"))
    if incorporation_date:
        stock.incorporation_date = incorporation_date
        update_fields.append("incorporation_date")
    if update_fields:
        stock.save(update_fields=update_fields)


def upsert_from_ngx_data(data: dict[str, Any]) -> CompanyProfile | None:
    symbol = data.get("Symbol")
    if not symbol:
        return None

    stock, _ = Stock.objects.get_or_create(
        symbol=symbol,
        defaults={
            "company": data.get("CompanyName", symbol),
            "active": True,
        },
    )
    _sync_stock_from_ngx(stock, data)

    profile, _ = CompanyProfile.objects.update_or_create(
        stock=stock,
        defaults=_profile_field_values(data),
    )
    return profile


def build_overview_dict(profile: CompanyProfile, stock: Stock) -> dict[str, Any]:
    prev_close = _to_float(profile.prev_close)
    shares_outstanding = _to_float(profile.shares_outstanding)
    date_of_incorporation = profile.date_of_incorporation
    if date_of_incorporation is None and profile.raw_ngx_data:
        date_of_incorporation = profile.raw_ngx_data.get("DateOfIncorporation")

    return {
        "marketcap": prev_close * shares_outstanding,
        "CompanyName": profile.company_name or stock.company,
        "Sector": stock.sector or "",
        "SubSector": profile.sub_sector,
        "dividend": _to_float(profile.dividend),
        "MarketClassification": profile.market_classification,
        "DateOfIncorporation": date_of_incorporation,
        "Website": profile.website,
        "NatureofBusiness": profile.nature_of_business,
        "CompanyAddress": profile.company_address,
        "Telephone": profile.telephone,
        "HIGH52WK_PRICE": (
            _to_float(profile.high_52wk_price) if profile.high_52wk_price else None
        ),
        "LOW52WK_PRICE": (
            _to_float(profile.low_52wk_price) if profile.low_52wk_price else None
        ),
        "BoardOfDirectors": profile.board_of_directors,
        "Email": profile.email,
    }


def get_empty_overview() -> dict[str, Any]:
    return EMPTY_OVERVIEW.copy()


def get_symbol_overview(symbol: str) -> dict[str, Any]:
    try:
        profile = CompanyProfile.objects.select_related("stock").get(
            stock__symbol=symbol
        )
        return build_overview_dict(profile, profile.stock)
    except CompanyProfile.DoesNotExist:
        try:
            stock = Stock.objects.get(symbol=symbol)
            overview = get_empty_overview()
            overview["CompanyName"] = stock.company
            overview["Sector"] = stock.sector or ""
            return overview
        except Stock.DoesNotExist:
            return get_empty_overview()


def get_shares_outstanding(symbol: str) -> float:
    profile = (
        CompanyProfile.objects.filter(stock__symbol=symbol)
        .values_list("shares_outstanding", flat=True)
        .first()
    )
    return _to_float(profile)


def get_all_shares_outstanding() -> dict[str, float]:
    rows = CompanyProfile.objects.filter(
        stock__active=True,
        shares_outstanding__isnull=False,
    ).values_list("stock__symbol", "shares_outstanding")
    return {symbol: _to_float(shares) for symbol, shares in rows}
