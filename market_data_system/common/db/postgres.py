from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

from common.utils.config import settings
from common.logging.logger import get_logger

logger = get_logger(__name__)

Base = declarative_base()


class Stock(Base):
    __tablename__ = "portfolio_stock"

    id = Column(Integer, primary_key=True)
    company = Column(String)
    symbol = Column(String)
    sector = Column(String, nullable=True)
    listing_date = Column(Date, nullable=True)
    incorporation_date = Column(Date, nullable=True)
    created = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)


class PostgresDB:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PostgresDB, cls).__new__(cls)
            cls._instance._initialize_connection()
        return cls._instance

    def _initialize_connection(self):
        """Initialize PostgreSQL connection."""
        try:
            self.engine = create_engine(settings.postgres_url)
            self.Session = sessionmaker(bind=self.engine)
            logger.info("PostgreSQL connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def get_active_stocks(self):
        """Get all active stocks from the database."""
        session = self.Session()
        try:
            stocks = session.query(Stock).filter(Stock.active == True).all()
            return stocks
        except Exception as e:
            logger.error(f"Failed to get active stocks: {e}")
            raise
        finally:
            session.close()

    def update_stock_active_status(self, symbol, active):
        """Update the active status of a stock."""
        session = self.Session()
        try:
            stock = session.query(Stock).filter(Stock.symbol == symbol).first()
            if stock:
                stock.active = active
                session.commit()
                logger.info(f"Updated stock {symbol} active status to {active}")
                return True
            else:
                logger.warning(f"Stock {symbol} not found in database")
                return False
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update stock {symbol} active status: {e}")
            return False
        finally:
            session.close()


# Create a singleton instance
postgres_db = PostgresDB()
