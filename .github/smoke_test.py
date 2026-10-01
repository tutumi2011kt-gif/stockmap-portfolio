from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

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
  window.__avCalls = 0;
  window.__tdCalls = 0;
  const bySymbol = {
    TSLA: {name:'Tesla, Inc.', cap:'1500000000000', growth:'0.32', eps:'3.50', ps:'13.2', per:'125', peg:'2.4', price:'500.00', volume:'25000000'},
    IONQ: {name:'IonQ, Inc.', cap:'16000000000', growth:'0.85', eps:'-0.80', ps:'45.0', per:'None', peg:'None', price:'70.00', volume:'8000000'}
  };

  window.fetch = async (url, opts={}) => {
    const s = String(url);

    if (s.includes('api.twelvedata.com/quote')) {
      window.__tdCalls++;
      const auth = (opts.headers || {})['Authorization'];
      if (auth !== 'apikey TD_TEST_KEY') {
        return {ok:false,status:401,json:async()=>({status:'error',message:'bad auth'})};
      }
      const u = new URL(s);
      const symbol = u.searchParams.get('symbol');
      const d = bySymbol[symbol] || bySymbol.TSLA;
      return {ok:true,status:200,json:async()=>({
        symbol, name:d.name, exchange:'NASDAQ', currency:'USD',
        datetime:'2026-10-01', close:d.price, volume:d.volume,
        previous_close:symbol==='TSLA'?'490.00':'68.00',
        percent_change:symbol==='TSLA'?'2.04':'2.94',
        average_volume:symbol==='TSLA'?'22000000':'7000000',
        is_market_open:false,
        fifty_two_week:{low:'180.00',high:'550.00'}
      })};
    }

    if (s.includes('alphavantage.co/query')) {
      window.__avCalls++;
      const u = new URL(s);
      const fn = u.searchParams.get('function');
      const symbol = u.searchParams.get('symbol');
      const key = u.searchParams.get('apikey');
      if (key !== 'AV_TEST_KEY') return {ok:true,status:200,json:async()=>({Information:'invalid key'})};
      const d = bySymbol[symbol] || bySymbol.TSLA;
      if (fn === 'OVERVIEW') {
        return {ok:true,status:200,json:async()=>({
          Symbol:symbol, Name:d.name, MarketCapitalization:d.cap,
          QuarterlyRevenueGrowthYOY:d.growth, EPS:d.eps,
          PriceToSalesRatioTTM:d.ps, PERatio:d.per, PEGRatio:d.peg,
          Sector:'TECHNOLOGY', Industry:'TEST INDUSTRY', Currency:'USD',
          Exchange:'NASDAQ', Country:'USA', RevenueTTM:'100000000000',
          QuarterlyEarningsGrowthYOY:'0.25', ProfitMargin:'0.12', Beta:'1.8',
          '50DayMovingAverage':'430', '200DayMovingAverage':'350',
          AnalystTargetPrice:'520', SharesOutstanding:'3000000000',
          DividendYield:'0'
        })};
      }
    }

    return realFetch(url, opts);
  };
})();
"""
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": mock_js})

try:
    driver.get("http://127.0.0.1:8000/")
    assert "StockMap Portfolio" in driver.title
    driver.execute_script("localStorage.setItem('stockmap_alpha_vantage_key','AV_TEST_KEY')")
    driver.execute_script("localStorage.setItem('stockmap_twelve_data_key','TD_TEST_KEY')")

    # Portfolio: TSLA + private holding information
    driver.find_element(By.ID, "pTicker").send_keys("TSLA")
    driver.find_element(By.ID, "pAdd").click()
    wait.until(lambda d: d.find_element(By.ID, "edit").get_attribute("open") is not None)
    for field, value in {"eShares":"10","eAvg":"300"}.items():
        el = driver.find_element(By.ID, field)
        el.clear()
        el.send_keys(value)
    driver.find_element(By.ID, "saveEdit").click()
    wait.until(lambda d: "TSLA" in d.find_element(By.ID, "pBody").text)

    # Watchlist: IONQ + private memo
    driver.find_element(By.CSS_SELECTOR, '[data-page="watch"]').click()
    driver.find_element(By.ID, "wTicker").send_keys("IONQ")
    driver.find_element(By.ID, "wAdd").click()
    wait.until(lambda d: d.find_element(By.ID, "edit").get_attribute("open") is not None)
    driver.find_element(By.ID, "saveEdit").click()
    driver.find_element(By.XPATH, '//*[@id="wList"]//button[contains(.,"詳細")]').click()
    driver.find_element(By.XPATH, '//*[@id="wDetail"]//button[contains(.,"メモ")]').click()
    ta = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#wtab textarea")))
    ta.send_keys("決算後に成長率を確認。押し目で再検討。")
    time.sleep(0.2)

    # First bulk refresh uses BOTH providers for both tickers.
    driver.find_element(By.CSS_SELECTOR, '[data-page="portfolio"]').click()
    driver.find_element(By.ID, "updateAllBtn").click()
    wait.until(lambda d: d.find_element(By.ID, "updateAllBtn").is_enabled())
    saved = driver.execute_script("return JSON.parse(localStorage.getItem('stockmap_v1'))")
    tsla = next(x for x in saved["portfolio"] if x["ticker"] == "TSLA")
    ionq = next(x for x in saved["watch"] if x["ticker"] == "IONQ")

    assert float(tsla["price"]) == 500.0
    assert float(tsla["volume"]) == 25000000
    assert float(tsla["averageVolume"]) == 22000000
    assert float(tsla["high52"]) == 550.0
    assert float(tsla["cap"]) == 1500.0
    assert float(tsla["growth"]) == 32.0
    assert float(tsla["ps"]) == 13.2
    assert tsla["sector"] == "TECHNOLOGY"
    assert float(ionq["price"]) == 70.0
    assert float(ionq["growth"]) == 85.0

    # Private user-entered data stays untouched.
    assert float(tsla["shares"]) == 10.0
    assert float(tsla["avg"]) == 300.0
    assert "決算後に成長率を確認" in ionq["memo"]

    av1 = driver.execute_script("return window.__avCalls")
    td1 = driver.execute_script("return window.__tdCalls")
    assert av1 == 2
    assert td1 == 2

    # Second bulk refresh: quotes refresh again, fundamentals are cached for 24h.
    driver.find_element(By.ID, "updateAllBtn").click()
    wait.until(lambda d: d.find_element(By.ID, "updateAllBtn").is_enabled())
    av2 = driver.execute_script("return window.__avCalls")
    td2 = driver.execute_script("return window.__tdCalls")
    assert av2 == 2
    assert td2 == 4
    assert "指標キャッシュ" in driver.find_element(By.ID, "updateAllStatus").text

    # Single-security refresh forces both quote and fundamentals.
    driver.find_element(By.XPATH, '//*[@id="pBody"]//button[contains(.,"編集")]').click()
    wait.until(lambda d: d.find_element(By.ID, "edit").get_attribute("open") is not None)
    driver.find_element(By.ID, "updateOneBtn").click()
    wait.until(lambda d: d.find_element(By.ID, "updateOneBtn").is_enabled())
    assert "更新完了" in driver.find_element(By.ID, "updateOneStatus").text
    assert driver.execute_script("return window.__avCalls") == 3
    assert driver.execute_script("return window.__tdCalls") == 5

    # Keys are stored separately from portfolio state.
    saved = driver.execute_script("return JSON.parse(localStorage.getItem('stockmap_v1'))")
    assert "apiKey" not in saved
    assert driver.execute_script("return localStorage.getItem('stockmap_alpha_vantage_key')") == "AV_TEST_KEY"
    assert driver.execute_script("return localStorage.getItem('stockmap_twelve_data_key')") == "TD_TEST_KEY"

    # Settings shows both provider fields.
    driver.find_element(By.ID, "closeEdit").click()
    driver.find_element(By.CSS_SELECTOR, '[data-page="settings"]').click()
    assert driver.find_element(By.ID, "tdKeyInput").is_displayed()
    assert driver.find_element(By.ID, "avKeyInput").is_displayed()

    # Persistence after reload.
    driver.refresh()
    wait.until(EC.presence_of_element_located((By.ID, "pTicker")))
    driver.find_element(By.CSS_SELECTOR, '[data-page="portfolio"]').click()
    assert "TSLA" in driver.find_element(By.ID, "pBody").text

    print("SMOKE_TEST_OK")
finally:
    driver.quit()
