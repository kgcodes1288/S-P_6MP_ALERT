import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json, os



# Step 1: Get S&P 500 tickers from Wikipedia
def get_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Find the table containing S&P 500 tickers
    table = soup.find("table", {"id": "constituents"})
    df = pd.read_html(str(table))[0]  # Read into a DataFrame
    tickers = df[["Symbol", "Security"]].to_dict(orient="records")

    return tickers[:50]


# Step 2: Fetch stock data using yfinance
def get_stock_data(tickers):
    stock_data = []
    
    sleepy_time = 1.5
    for i,item in enumerate(tickers):
        time.sleep(sleepy_time)
        if i % 30 == 0:
            time.sleep(15)
        ticker = item["Symbol"]
        company_name = item["Security"]
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            price = stock.history(period="1d")["Close"].iloc[-1] if not stock.history(period="1d").empty else "N/A"
            market_cap = info.get("marketCap", "N/A")
            eps = info.get("trailingEps", "N/A")
            pe_ratio = info.get("trailingPE", "N/A")
            sector = info["sector"]
            industry = stock.info["industry"]

            # Fetch Cash on Hand from balance sheet
            balance_sheet = stock.balance_sheet
            cash_on_hand = "N/A"
            if not balance_sheet.empty:
                try:
                    cash_on_hand = balance_sheet.loc["Cash And Cash Equivalents", :].iloc[0]
                except KeyError:
                    cash_on_hand = "N/A"

            # Fetch past 6 months peak
            history_6m = stock.history(period="6mo")
            peak_6m = history_6m["High"].max() if not history_6m.empty else "N/A"

            stock_data.append({
                "Ticker": ticker,
                "Price": price,
                "Company Name": company_name,
                "Market Cap": market_cap,
                "EPS": eps,
                "Cash on Hand": cash_on_hand,
                "6M Peak Price": peak_6m,
                "PE Ratio": pe_ratio,
                "Sector": sector,
                "Industry": industry
            })
            sleepy_time = 1.5
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            if 'Try after a while' in str(e):
                sleepy_time = 10
    return pd.DataFrame(stock_data)


# Get tickers and fetch stock prices
try:
    sp500_tickers = get_sp500_tickers()
except:
    with open('S_P_500.json', 'r') as f:
        sp500_tickers = json.load(f)
stock_prices_df = get_stock_data(sp500_tickers)
print("Got All Stocks Data")


stock_prices_df = stock_prices_df[stock_prices_df['Price'] != 'N/A']
stock_prices_df = stock_prices_df[~stock_prices_df['Price'].isna()]

stock_prices_df = stock_prices_df[stock_prices_df['6M Peak Price'] != 'N/A']
stock_prices_df = stock_prices_df[~stock_prices_df['6M Peak Price'].isna()]

stock_prices_df['Change from 6 month Peak'] = stock_prices_df.apply(lambda r: (r['Price']-r['6M Peak Price'])/r['6M Peak Price'], axis=1)
stock_prices_df["Rank"] = stock_prices_df.groupby("Sector")["Change from 6 month Peak"].rank(method="dense", ascending=True)

stock_prices_df = stock_prices_df[stock_prices_df["Rank"] <= 25]
stock_prices_df = stock_prices_df.sort_values(by=['Sector','Rank'])
stock_prices_df = stock_prices_df.drop(columns=['Rank'])


# Function to format numbers as currency
def format_currency(value):
    if isinstance(value, (int, float)) and value != "N/A":
        return f"${value:,.2f}"  # Formats as "$1,234.56"
    return value


def format_percentage(value):
    return f"{value:.2%}"


GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")




def dataframe_to_html(df):
    df_html = '<table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; font-family: Arial;">'
    df_html += "<tr style='background-color: #f2f2f2;'><th>Company Name</th><th>Ticker</th><th>Price</th><th>Market Cap</th><th>EPS</th><th>PE Ratio</th><th>Cash on Hand</th><th>6M Peak Price</th><th>Change from 6 month Peak</th><th>Industry</th></tr>"

    for _, row in df.iterrows():
        # Apply color coding based on value
        def get_color(value):
            if value == "N/A":
                return "gray"
            elif isinstance(value, (int, float)):
                return "green" if value > 0 else "red"
            return "black"

        df_html += f"""
        <tr>
            <td>{row['Company Name']}</td>
            <td>{row['Ticker']}</td>
            <td>{format_currency(row['Price'])}</td>
            <td>{format_currency(row['Market Cap'])}</td>
            <td style="color: {get_color(row['EPS'])};">{format_currency(row['EPS'])}</td>
            <td style="color: {get_color(row["PE Ratio"])};">{row["PE Ratio"]}</td>
            <td">{format_currency(row['Cash on Hand'])}</td>
            <td">{format_currency(row['6M Peak Price'])}</td>
            <td style="color: {get_color(row['Change from 6 month Peak'])};">{format_percentage(row['Change from 6 month Peak'])}</td>
            <td>{row['Industry']}</td>
        </tr>
        """
    df_html += "</table>"
    return df_html


def send_email(subject, body, recipient_email):
    for email in recipient_email:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_USER
        msg["To"] = email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "html"))

        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                # server.starttls()
                server.login(GMAIL_USER, GMAIL_PASS)
                server.sendmail(GMAIL_USER, email, msg.as_string())
                server.quit()
            print("✅ Email sent successfully!")
        except Exception as e:
            print(f"❌ Failed to send email: {e}")


email_body = "<h2>S&P 500 Stock Data by Sector</h2><br>"
# Convert to HTML
for sector in stock_prices_df['Sector'].unique():
    temp = stock_prices_df[stock_prices_df['Sector'] ==sector]
    email_body_temp = f"""
    {dataframe_to_html(temp)}
    """
    email_body = email_body + '<h2>{}</h2>'.format(sector)
    email_body = email_body + email_body_temp + '<br>'

email_body = email_body + "<p>Best regards,<br>Your Stock Bot</p>"
# Send email
recipient_emails = [os.getenv("KG"),os.getenv("DRE"),os.getenv("JAMES"),os.getenv("STEPH")]  # Replace with the actual recipient email
print("Sending email")
send_email("📈 S&P 500 Stock Data Report Top 25 Opps per sector", email_body, recipient_emails)


