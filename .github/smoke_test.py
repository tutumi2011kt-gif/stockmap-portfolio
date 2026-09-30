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
wait = WebDriverWait(driver, 10)

try:
    driver.get("http://127.0.0.1:8000/")
    assert "StockMap Portfolio" in driver.title

    # Portfolio: add TSLA
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
    assert "TSLA" in driver.find_element(By.ID, "pBody").text

    # Watchlist: add IONQ
    driver.find_element(By.CSS_SELECTOR, '[data-page="watch"]').click()
    wait.until(EC.visibility_of_element_located((By.ID, "wTicker")))
    driver.find_element(By.ID, "wTicker").send_keys("IONQ")
    driver.find_element(By.ID, "wAdd").click()
    wait.until(lambda d: d.find_element(By.ID, "edit").get_attribute("open") is not None)

    for field, value in {"eGrowth":"80","ePS":"40"}.items():
        el = driver.find_element(By.ID, field)
        el.clear()
        el.send_keys(value)

    driver.find_element(By.ID, "saveEdit").click()
    wait.until(lambda d: "IONQ" in d.find_element(By.ID, "wList").text)

    # Detail + memo
    driver.find_element(By.XPATH, '//*[@id="wList"]//button[contains(.,"詳細")]').click()
    wait.until(EC.presence_of_element_located((By.ID, "wDetail")))
    driver.find_element(By.XPATH, '//*[@id="wDetail"]//button[contains(.,"メモ")]').click()
    ta = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#wtab textarea")))
    ta.send_keys("決算後に成長率を確認。押し目で再検討。")
    time.sleep(0.3)
    assert "決算後に成長率を確認" in driver.find_element(By.ID, "wList").text

    # Persistence after reload
    driver.refresh()
    wait.until(EC.presence_of_element_located((By.ID, "pTicker")))
    driver.find_element(By.CSS_SELECTOR, '[data-page="portfolio"]').click()
    wait.until(lambda d: "TSLA" in d.find_element(By.ID, "pBody").text)
    assert "TSLA" in driver.find_element(By.ID, "pBody").text

    print("SMOKE_TEST_OK")
finally:
    driver.quit()
