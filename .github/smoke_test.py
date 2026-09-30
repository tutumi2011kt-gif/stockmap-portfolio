from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, json

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--window-size=1280,900")

driver = webdriver.Chrome(options=opts)
wait = WebDriverWait(driver, 15)

mock_js = r"""
(() => {
  const realFetch = window.fetch.bind(window);
  window.fetch = async (url, opts) => {
    const s = String(url);
    if (!s.includes('alphavantage.co/query')) return realFetch(url, opts);
    const u = new URL(s);
    const fn = u.searchParams.get('function');
    const symbol = u.searchParams.get('symbol');
    const bySymbol = {
      TSLA: {name:'Tesla, Inc.', cap:'1500000000000', growth:'0.32', eps:'3.50', ps:'13.2', per:'125', peg:'2.4', price:'500.00', volume:'25000000'},
      IONQ: {name:'IonQ, Inc.', cap:'16000000000', growth:'0.85', eps:'-0.80', ps:'45.0', per:'None', peg:'None', price:'70.00', volume:'8000000'}
    };
    const d = bySymbol[symbol] || bySymbol.TSLA;
    let body = {};
    if (fn === 'OVERVIEW') {
      body = {
        Symbol:symbol, Name:d.name, MarketCapitalization:d.cap,
        QuarterlyRevenueGrowthYOY:d.growth, EPS:d.eps,
        PriceToSalesRatioTTM:d.ps, PERatio:d.per, PEGRatio:d.peg,
        Sector:'TECHNOLOGY', Industry:'TEST INDUSTRY', Currency:'USD',
        Exchange:'NASDAQ', Country:'USA', RevenueTTM:'100000000000',
        QuarterlyEarningsGrowthYOY:'0.25', ProfitMargin:'0.12', Beta:'1.8',
        '52WeekHigh':'550', '52WeekLow':'180', '50DayMovingAverage':'430',
        '200DayMovingAverage':'350', AnalystTargetPrice:'520',
        SharesOutstanding:'3000000000', DividendYield:'0'
      };
    } else if (fn === 'GLOBAL_QUOTE') {
      body = {'Global Quote':{
        '01. symbol':symbol,'05. price':d.price,'06. volume':d.volume,
        '07. latest trading day':'2026-10-01','08. previous close':'490.00',
        '10. change percent':'2.04%'
      }};
    }
    return {ok:true,status:200,json:async()=>body};
  };
})();
"""
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": mock_js})

try:
    driver.get("http://127.0.0.1:8000/")
    assert "StockMap Portfolio" in driver.title
    driver.execute_script("localStorage.setItem('stockmap_alpha_vantage_key','TEST_KEY')")

    # Portfolio: add TSLA with private holding information
    driver.find_element(By.ID, "pTicker").send_keys("TSLA")
    driver.find_element(By.ID, "pAdd").click()
    wait.until(lambda d: d.find_element(By.ID, "edit").get_attribute("open") is not None)
    assert driver.find_element(By.ID, "eTicker").get_attribute("value") == "TSLA"

    for field, value in {
        "ePrice":"450","eGrowth":"28","ePS":"12","ePER":"120",
        "ePEG":"2","eShares":"10","eAvg":"300"
    }.items():
        el = driver.find_element(By.ID, field)
        el.clear()
        el.send_keys(value)

    driver.find_element(By.ID, "saveEdit").click()
    wait.until(lambda d: "TSLA" in d.find_element(By.ID, "pBody").text)

    # Watchlist: add IONQ and a private memo
    driver.find_element(By.CSS_SELECTOR, '[data-page="watch"]').click()
    wait.until(EC.visibility_of_element_located((By.ID, "wTicker")))
    driver.find_element(By.ID, "wTicker").send_keys("IONQ")
    driver.find_element(By.ID, "wAdd").click()
    wait.until(lambda d: d.find_element(By.ID, "edit").get_attribute("open") is not None)
    driver.find_element(By.ID, "saveEdit").click()
    wait.until(lambda d: "IONQ" in d.find_element(By.ID, "wList").text)
    driver.find_element(By.XPATH, '//*[@id="wList"]//button[contains(.,"詳細")]').click()
    driver.find_element(By.XPATH, '//*[@id="wDetail"]//button[contains(.,"メモ")]').click()
    ta = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#wtab textarea")))
    ta.send_keys("決算後に成長率を確認。押し目で再検討。")
    time.sleep(0.2)

    # Bulk update: portfolio + watchlist in one action
    driver.find_element(By.CSS_SELECTOR, '[data-page="portfolio"]').click()
    driver.find_element(By.ID, "updateAllBtn").click()
    wait.until(lambda d: d.find_element(By.ID, "updateAllBtn").is_enabled())
    wait.until(lambda d: "銘柄更新" in d.find_element(By.ID, "updateAllStatus").text)

    saved = driver.execute_script("return JSON.parse(localStorage.getItem('stockmap_v1'))")
    tsla = next(x for x in saved["portfolio"] if x["ticker"] == "TSLA")
    ionq = next(x for x in saved["watch"] if x["ticker"] == "IONQ")

    # Public data refreshed
    assert float(tsla["price"]) == 500.0
    assert float(tsla["cap"]) == 1500.0
    assert float(tsla["growth"]) == 32.0
    assert float(tsla["ps"]) == 13.2
    assert tsla["sector"] == "TECHNOLOGY"
    assert float(ionq["price"]) == 70.0
    assert float(ionq["growth"]) == 85.0

    # Private data must NOT be overwritten by refresh
    assert float(tsla["shares"]) == 10.0
    assert float(tsla["avg"]) == 300.0
    assert "決算後に成長率を確認" in ionq["memo"]

    # Single-security update button works
    driver.find_element(By.XPATH, '//*[@id="pBody"]//button[contains(.,"編集")]').click()
    wait.until(lambda d: d.find_element(By.ID, "edit").get_attribute("open") is not None)
    driver.find_element(By.ID, "updateOneBtn").click()
    wait.until(lambda d: d.find_element(By.ID, "updateOneBtn").is_enabled())
    assert "更新完了" in driver.find_element(By.ID, "updateOneStatus").text

    # API key stays outside portfolio backup state
    saved = driver.execute_script("return JSON.parse(localStorage.getItem('stockmap_v1'))")
    assert "apiKey" not in saved
    assert driver.execute_script("return localStorage.getItem('stockmap_alpha_vantage_key')") == "TEST_KEY"

    # Persistence
    driver.find_element(By.ID, "closeEdit").click()
    driver.refresh()
    wait.until(EC.presence_of_element_located((By.ID, "pTicker")))
    assert "TSLA" in driver.find_element(By.ID, "pBody").text

    print("SMOKE_TEST_OK")
finally:
    driver.quit()
