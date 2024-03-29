from lumibot.brokers import Alpaca
from lumibot.backtesting import PolygonDataBacktesting
from lumibot.strategies.strategy import Strategy
from lumibot.traders import Trader
from datetime import datetime as dt
from alpaca_trade_api import REST
from timedelta import Timedelta
from finbert_utils import estimate_sentiment

from config import ALPACA_CREDS, BASE_URL, POLYGON_API_KEY

class MovingCrossOverML(Strategy):
    def initialize(self, symbol:str="DIA", cash_at_risk:float=.5):
        self.symbol = symbol
        self.sleeptime = "180M"
        self.last_trade = None
        self.cash_at_risk = cash_at_risk
        self.api = REST(base_url=BASE_URL,
                        key_id=ALPACA_CREDS['API_KEY'],
                        secret_key=ALPACA_CREDS['API_SECRET'])

    def position_sizing(self):
        cash = self.get_cash()
        last_price = self.get_last_price(self.symbol)
        quantity = round(cash * self.cash_at_risk / last_price,0)
        return cash, last_price, quantity

    def get_dates(self):
        today = self.get_datetime()
        three_days_prior = today - Timedelta(days=3)
        return today.strftime('%Y-%m-%d'), three_days_prior.strftime('%Y-%m-%d')

    def get_sentiment(self):
        today, three_days_prior = self.get_dates()
        news = self.api.get_news(symbol=self.symbol,
                                 start=three_days_prior,
                                 end=today)
        news = [ev.__dict__["_raw"]["headline"] for ev in news]
        probability, sentiment = estimate_sentiment(news)
        return probability, sentiment

    def on_trading_iteration(self):
        cash, last_price, quantity = self.position_sizing()
        probability, sentiment = self.get_sentiment()

        if cash > last_price:
            if sentiment == "positive" and probability > .90:
                if self.last_trade == "sell":
                    self.sell_all()
                order = self.create_order(
                    self.symbol,
                    quantity,
                    "buy",
                    type="bracket",
                    take_profit_price=last_price*1.20,
                    stop_loss_price=last_price*.95
                )
                self.submit_order(order)
                self.last_trade = "buy"
            elif sentiment == "negative" and probability > .95:
                if self.last_trade == "buy":
                    self.sell_all()
                order = self.create_order(
                    self.symbol,
                    quantity,
                    "sell",
                    type="bracket",
                    take_profit_price=last_price*.8,
                    stop_loss_price=last_price*1.05
                )
                self.submit_order(order)
                self.last_trade = "sell"

# Backtesting Params
stock_sym = "DIA"
start_date = dt(2023,1,1)
end_date = dt(2023,12,31)

# Data Stream
trader = Trader(backtest=True)
polygon_data = PolygonDataBacktesting(
    datetime_start=start_date,
    datetime_end=end_date,
    api_key=POLYGON_API_KEY,
    has_paid_subscription=False)

broker = Alpaca(ALPACA_CREDS, data_source=polygon_data)
strategy = MovingCrossOverML(name='with_ML', broker=broker,
                             parameters={"symbol":stock_sym,
                                         "cash_at_risk":.5},
                             benchmark_asset="SPY")
# Backtest
trader.add_strategy(strategy)
trader.run_all()


# Deployment
# trader = Trader()
# trader.add_strategy(strategy)
# trader.run_all()
