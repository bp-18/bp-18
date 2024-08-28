from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from datetime import datetime
import requests
import json


def crawl(radius):
    """
    지정한 반경 내의 음식점 정보를 크롤링하여 JSON 파일로 저장하는 함수

    Parameters:
        radius: 크롤링할 반경

    Returns:
        저장된 JSON 파일 경로
    """

    # 원격 크롬 드라이버 설정
    options = webdriver.ChromeOptions()
    options.add_argument('--headless') 
    options.add_argument('--ignore-ssl-errors=yes')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')
    options.add_argument('--log-level=3')
    options.add_argument('--disable-gpu')
    options.add_argument('--incognito')

    # 로딩 시간 줄이기 위한 이미지 로딩 비활성화
    options.add_argument('--disable-images')
    options.add_experimental_option(
        "prefs", {'profile.managed_default_content_settings.images': 2})
    options.add_argument('--blink-settings=imagesEnabled=false')
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.200'
    options.add_argument(f'user-agent={user_agent}')

    # 크롬 웹 드라이버 실행
    driver = webdriver.Chrome(options=options)

    # 네이버 지도 URL 설정 (반경 반영)
    url = f"https://map.naver.com/p/search/음식점?c={radius},0,0,0,dh"
    driver.get(url)
    driver.maximize_window()

    # 페이지 로드 대기
    time.sleep(1)

    # 검색 결과 iframe으로 전환
    driver.switch_to.frame("searchIframe")
    # 옵션 버튼이 등장할 때까지 대기(명시적 대기)
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "._restaurant_filter_item:first-child > a"))
    )

    # 옵션 버튼 클릭
    option_btn = driver.find_element(By.CSS_SELECTOR, "._restaurant_filter_item:first-child > a")
    option_btn.send_keys(Keys.ENTER)

    # '인기 많은 순' 버튼 클릭
    most_btn = driver.find_element(By.CSS_SELECTOR, "#_popup_rank+div > span:first-child > a")
    most_btn.send_keys(Keys.ENTER)

    # '영업 중' 버튼 클릭
    working_btn = driver.find_element(By.CSS_SELECTOR, "#_popup_property+div > span:first-child > a")
    working_btn.send_keys(Keys.ENTER)

    # 검색 결과 버튼 클릭
    result_btn = driver.find_element(By.CSS_SELECTOR, ".qeVvz a:last-child")
    result_btn.send_keys(Keys.ENTER)
    time.sleep(1)

    # 스크롤 다운하여 추가 데이터 로드
    for _ in range(10):
        element = driver.find_elements(By.CSS_SELECTOR, "#_pcmap_list_scroll_container > ul > li")[-1]
        driver.execute_script("arguments[0].scrollIntoView(true);", element)

    # 페이지 소스 가져오기
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    # 드라이버 종료
    driver.quit()

    # 음식점 이름과 메뉴 추출
    restaurant_names = [restaurant_name.text for restaurant_name in soup.select(".place_bluelink")]
    restaurant_menus = [restaurant_menu.text for restaurant_menu in soup.select(".KCMnt")]

    # 음식점 데이터를 저장할 딕셔너리 초기화
    restaurant_data = {}

    # 평점, 프로그램 출연 정보, 리뷰 수 크롤링
    for i, name in enumerate(restaurant_names):
        restaurant_container = f"#_pcmap_list_scroll_container ul li:nth-child({i+1}) .MVx6e"
        restaurant_rate = soup.select(f"{restaurant_container} .orXYY")
        restaurant_program = soup.select(f"{restaurant_container} .V1dzc")
        restaurant_review = soup.select(f"{restaurant_container} > span:nth-last-child(1)")

        restaurant_data[name] = {}
        restaurant_data[name]["menu"] = restaurant_menus[i]

        # 평점 정보가 없는 경우 None으로 설정
        if restaurant_rate == []:
            restaurant_data[name]["rate"] = None
        else:
            restaurant_data[name]["rate"] = float(restaurant_rate[0].text.lstrip("별점"))

        # 프로그램 정보가 없는 경우 None으로 설정
        if restaurant_program == []:
            restaurant_data[name]["program"] = None
        else:
            restaurant_data[name]["program"] = restaurant_program[0].text.lstrip("TV")

        # 리뷰 정보가 없는 경우 None으로 설정, 오류 발생 시 재시도
        try:
            restaurant_data[name]["review"] = int(restaurant_review[0].text.lstrip("리뷰 ").rstrip("+"))
        except ValueError:
            try:
                restaurant_review = soup.select(f"{restaurant_container} > span:nth-last-child(2)")
                restaurant_data[name]["review"] = int(restaurant_review[0].text.lstrip("리뷰 ").rstrip("+"))
            except ValueError:
                restaurant_data[name]["review"] = None

    # 현재 시간에 따라 파일 이름 설정
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = f"crawled_data_{current_time}.json"

    # JSON 파일로 저장
    json_data = json.dumps(restaurant_data, indent=2, ensure_ascii=False)
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(json_data)

    return save_path


def school_meal_crawler(place):
    """
    학식 정보를 크롤링하여 dictionary에 담아주는 함수

    Parameters:
        place: 크롤링 할 학교 식당

    Returns:
        학식 정보를 담은 dictionary
    """

    # 학교 식당, 시간대를 반영하여 mealtify 웹페이지 접속 후 html parsing
    url = f"https://www.mealtify.com/univ/cau/{place}/meal/today"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    # 학식 메뉴와 메뉴의 타입을 크롤링하여 리스트에 저장
    school_menus = [school_menu.text for school_menu in soup.select(".pt-4 tbody tr td:nth-child(1)")]
    school_types = [school_type.text for school_type in soup.select(".pt-4 tbody tr td:nth-child(1)")]

    # 만일 참슬기식당이라면 특식과 한식을 나누어 dictionary에 저장
    if place == "truly-wise":
        school_return_data = {
            "A": {
                "menu": {}
            },
            "B": {
                "menu": {}
            }
        }
        kind_of_menu = "A"

        for i, menu in enumerate(school_menus):
            if "총 칼로리" in menu:
                kind_of_menu = "B"
                continue
            school_return_data[kind_of_menu]["menu"][menu] = {"type": school_types[i]}
    else:
        school_return_data = {
            "menu": {}
        }

        for i, menu in enumerate(school_menus):
            if "총 칼로리" in menu:
                continue
            school_return_data["menu"][menu] = {"type": school_types[i]}

    return school_return_data


def crawl_school_meal():
    """
    오늘의 학교 급식 메뉴를 크롤링하여 JSON 파일로 저장하는 함수

    Returns:
        저장된 JSON 파일 경로
    """

    # JSON에 저장할 dictionary
    school_restaurant_data = {}

    # 학교 식당 별 학식 정보 크롤링 후 dictionary에 저장
    school_restaurant_data["생활관식당(블루미르308관)"] = school_meal_crawler('blue-308')
    school_restaurant_data["생활관식당(블루미르309관)"] = school_meal_crawler('blue-309')
    school_restaurant_data["참슬기식당(310관 B4층)"] = school_meal_crawler('truly-wise')

    # 파일 명에 코드를 실행한 날짜와 시간을 반영
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = f"school_meal_{current_time}.json"

    # 학식 정보 dictionary를 문자열로 변환 후 JSON파일에 저장
    json_data = json.dumps(school_restaurant_data, indent=2, ensure_ascii=False)
    with open(save_path, 'w', encoding="utf-8") as f:
        f.write(json_data)

    return save_path


if __name__ == "__main__":
    # 음식점 크롤링 예시
    radius = 15  # 반경 15km
    print(f"Crawled restaurant data saved to: {crawl(radius)}")

    # 학식 크롤링 예시
    print(f"Crawled school meal data saved to: {crawl_school_meal()}")