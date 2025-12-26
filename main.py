# main.py
import mysql.connector
from mysql.connector import Error as MySQLError
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.common.exceptions import InvalidSessionIdException, WebDriverException
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import logging
from datetime import datetime
import sys
import os
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import streamlit as st
import hashlib
import pymysql
from pymysql.cursors import DictCursor

# 设置页面配置
st.set_page_config(
    page_title="考研AI问答系统",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'crawler_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# 全局数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'your_password',
    'database': 'kaoyan_data'
}


class ThreadSafeSpider:
    """线程安全的爬虫类"""

    def __init__(self, thread_id=0):
        self.thread_id = thread_id
        self.retry_count = 0
        self.max_retries = 3
        self.setup_driver()

    def setup_driver(self):
        """配置Edge浏览器驱动"""
        edge_options = Options()

        # 基本设置
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--disable-dev-shm-usage')
        edge_options.add_argument('--window-size=1920,1080')
        edge_options.add_argument('--disable-gpu')

        # 反检测设置
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        edge_options.add_argument('--disable-blink-features=AutomationControlled')

        # 禁用图片
        prefs = {'profile.default_content_setting_values': {'images': 2}}
        edge_options.add_experimental_option('prefs', prefs)

        edge_options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
        )

        try:
            driver_path = 'msedgedriver.exe'
            service = Service(driver_path)
            self.driver = webdriver.Edge(service=service, options=edge_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            # 超时时间
            self.driver.set_page_load_timeout(35)
            self.driver.implicitly_wait(7)
            self.wait = WebDriverWait(self.driver, 10)
            logging.info(f"线程 {self.thread_id} 浏览器驱动初始化成功")
        except Exception as e:
            logging.error(f"线程 {self.thread_id} 浏览器驱动初始化失败: {e}")
            raise

    def restart_driver(self):
        """重启浏览器驱动"""
        try:
            if hasattr(self, 'driver'):
                self.driver.quit()
        except:
            pass

        time.sleep(5)
        self.setup_driver()
        self.retry_count += 1
        logging.info(f"线程 {self.thread_id} 浏览器驱动已重启，重试次数: {self.retry_count}")

    def safe_execute(self, func, *args, **kwargs):
        """安全执行函数"""
        try:
            return func(*args, **kwargs)
        except (InvalidSessionIdException, WebDriverException, TimeoutException) as e:
            if self.retry_count < self.max_retries:
                logging.warning(f"线程 {self.thread_id} 浏览器会话失效，重启: {e}")
                self.restart_driver()
                time.sleep(3)
                return self.safe_execute(func, *args, **kwargs)
            else:
                logging.error(f"线程 {self.thread_id} 达到最大重试次数")
                raise
        except Exception as e:
            logging.error(f"线程 {self.thread_id} 执行函数时出错: {e}")
            raise

    def wait_for_element(self, by, value, timeout=10):
        """等待元素出现"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            return None

    def wait_for_element_clickable(self, by, value, timeout=10):
        """等待元素可点击"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            return element
        except TimeoutException:
            return None

    def crawl_school_majors(self, school_name, major_link=None, region=None, school_features=None,
                            search_type='region'):
        """爬取学校专业信息"""
        return self.safe_execute(self._crawl_school_majors_impl, school_name, major_link, region, school_features,
                                 search_type)

    def _crawl_school_majors_impl(self, school_name, major_link=None, region=None, school_features=None,
                                  search_type='region'):
        """爬取学校专业信息的实现"""
        all_majors_data = []

        # 搜索关键词
        search_keywords = [
            "计算机", "软件工程", "人工智能", "网络空间安全", "数据科学与大数据技术",
            "信息安全", "数学", "统计学", "医学", "药学", "护理学"
        ]

        try:
            logging.info(f"线程 {self.thread_id} 开始爬取 {school_name}")

            if major_link:
                self.driver.get(major_link)
                time.sleep(3)
            else:
                self.driver.get("https://yz.chsi.com.cn/zsml/dw.do")
                time.sleep(3)

                school_search_input = self.wait_for_element(
                    By.CSS_SELECTOR, "input[placeholder='请输入招生单位名称']"
                )
                if not school_search_input:
                    logging.error(f"线程 {self.thread_id} 未找到学校搜索框")
                    return []

                school_search_input.clear()
                school_search_input.send_keys(school_name)
                time.sleep(3)

                search_button = self.wait_for_element_clickable(
                    By.CSS_SELECTOR, "button.ivu-btn-primary"
                )
                if search_button:
                    search_button.click()
                    time.sleep(3)
                else:
                    logging.error(f"线程 {self.thread_id} 未找到查询按钮")
                    return []

                if self.check_no_results():
                    logging.warning(f"线程 {self.thread_id} 未找到学校: {school_name}")
                    return []

                # 提取地区信息和院校特性
                if search_type == 'school':
                    region = self.extract_region_from_school_page()
                    if not school_features:
                        school_features = self.extract_school_features_from_page()

                major_button = self.find_major_button()
                if major_button:
                    try:
                        button_href = major_button.get_attribute("href")
                        if button_href and "http" in button_href:
                            self.driver.get(button_href)
                            time.sleep(3)
                    except Exception as e:
                        logging.error(f"线程 {self.thread_id} 进入专业页面失败: {e}")
                        return []
                else:
                    logging.error(f"线程 {self.thread_id} 未找到开设专业按钮")
                    return []

            current_url = self.driver.current_url
            if "/zsml/dwzy.do" not in current_url:
                logging.error(f"线程 {self.thread_id} 不在专业页面")
                return []

            original_url = self.driver.current_url

            for keyword in search_keywords:
                try:
                    keyword_data = self.search_and_parse_majors(keyword, school_name, original_url, region,
                                                                school_features, search_type)
                    if keyword_data:
                        all_majors_data.extend(keyword_data)
                    time.sleep(2)
                except Exception as e:
                    logging.error(f"线程 {self.thread_id} 搜索关键词 {keyword} 时出错: {e}")
                    continue

            # 去重处理
            unique_majors = {}
            for data in all_majors_data:
                key = f"{data['school_name']}_{data['major_name']}_{data.get('major_code', '')}_{data.get('department', '')}"
                if key not in unique_majors:
                    unique_majors[key] = data

            all_majors_data = list(unique_majors.values())
            logging.info(f"线程 {self.thread_id} 去重后共获取 {len(all_majors_data)} 个唯一专业")

        except Exception as e:
            logging.error(f"线程 {self.thread_id} 爬取学校 {school_name} 失败: {e}")

        return all_majors_data

    def search_and_parse_majors(self, keyword, school_name, original_url, region, school_features, search_type):
        """搜索并解析专业信息"""
        return self.safe_execute(self._search_and_parse_majors_impl, keyword, school_name, original_url, region,
                                 school_features, search_type)

    def _search_and_parse_majors_impl(self, keyword, school_name, original_url, region, school_features, search_type):
        """搜索并解析专业信息的实现"""
        majors_data = []

        try:
            search_input = self.wait_for_element(
                By.CSS_SELECTOR, "input.ivu-input.ivu-input-default[placeholder='请输入专业名称']"
            )
            if not search_input:
                return []

            search_input.clear()
            search_input.send_keys(keyword)
            time.sleep(3)

            try:
                dropdown = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".ivu-select-dropdown"))
                )
                options = dropdown.find_elements(By.CSS_SELECTOR, ".ivu-select-item")

                for i in range(len(options)):
                    try:
                        search_input = self.wait_for_element(
                            By.CSS_SELECTOR, "input.ivu-input.ivu-input-default[placeholder='请输入专业名称']"
                        )
                        if not search_input:
                            continue

                        search_input.clear()
                        search_input.send_keys(keyword)
                        time.sleep(3)

                        dropdown = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".ivu-select-dropdown"))
                        )
                        current_options = dropdown.find_elements(By.CSS_SELECTOR, ".ivu-select-item")
                        if i < len(current_options):
                            current_option = current_options[i]
                            option_text = current_option.text.strip()

                            self.driver.execute_script("arguments[0].click();", current_option)
                            time.sleep(3)

                            page_data = self.parse_current_page_majors(school_name, keyword, option_text, region,
                                                                       school_features, search_type)
                            if page_data:
                                majors_data.extend(page_data)

                            self.driver.get(original_url)
                            time.sleep(3)

                    except StaleElementReferenceException:
                        continue
                    except Exception as e:
                        try:
                            self.driver.get(original_url)
                            time.sleep(3)
                        except:
                            pass
                        continue

            except TimeoutException:
                # 如果没有下拉选项，直接搜索
                search_button = self.wait_for_element_clickable(
                    By.CSS_SELECTOR, "button.ivu-btn-primary"
                )
                if search_button:
                    search_button.click()
                    time.sleep(3)

                    page_data = self.parse_current_page_majors(school_name, keyword, keyword, region, school_features,
                                                               search_type)
                    if page_data:
                        majors_data.extend(page_data)

                    self.driver.get(original_url)
                    time.sleep(3)

        except Exception as e:
            logging.error(f"线程 {self.thread_id} 搜索专业 {keyword} 失败: {e}")

        return majors_data

    def parse_current_page_majors(self, school_name, keyword, option_text, region, school_features, search_type):
        """解析当前页面的专业信息"""
        return self.safe_execute(self._parse_current_page_majors_impl, school_name, keyword, option_text, region,
                                 school_features, search_type)

    def _parse_current_page_majors_impl(self, school_name, keyword, option_text, region, school_features, search_type):
        """解析当前页面专业信息的实现"""
        majors_data = []

        try:
            self.expand_all_major_details()
            time.sleep(2)

            major_items = self.driver.find_elements(By.CSS_SELECTOR, ".zy-item")

            for item in major_items:
                try:
                    major_data = self.extract_major_basic_info(item)
                    if major_data and self.is_target_major(major_data['major_name']):
                        detailed_data_list = self.get_all_research_directions(item, school_name)

                        if detailed_data_list:
                            for detailed_data in detailed_data_list:
                                combined_data = major_data.copy()
                                combined_data.update(detailed_data)
                                combined_data.update({
                                    'school_name': school_name,
                                    'search_keyword': keyword,
                                    'selected_option': option_text,
                                    'region': region,
                                    'school_features': ', '.join(school_features) if school_features else '',
                                    'search_type': search_type,
                                    'data_source': f"研招网搜索 - {school_name} - {keyword}"
                                })
                                majors_data.append(combined_data)
                        else:
                            detailed_data = self.get_major_details_from_detail_page(item, school_name)
                            major_data.update(detailed_data)
                            major_data.update({
                                'school_name': school_name,
                                'search_keyword': keyword,
                                'selected_option': option_text,
                                'region': region,
                                'school_features': ', '.join(school_features) if school_features else '',
                                'search_type': search_type,
                                'data_source': f"研招网搜索 - {school_name} - {keyword}"
                            })
                            majors_data.append(major_data)

                except Exception:
                    continue

        except Exception as e:
            logging.error(f"线程 {self.thread_id} 解析页面专业失败: {e}")

        return majors_data

    def is_target_major(self, text):
        """检查是否为目标专业"""
        if not text:
            return False

        target_keywords = [
            "计算机科学与技术", "软件工程", "人工智能", "网络空间安全", "数据科学与大数据技术",
            "计算机应用技术", "信息安全", "数学与应用数学", "信息与计算科学", "应用数学",
            "统计学", "临床医学", "基础医学", "药学", "护理学"
        ]

        text_lower = text.lower()
        return any(keyword in text_lower for keyword in target_keywords)

    def get_all_research_directions(self, item, school_name):
        """获取专业的所有研究方向"""
        detailed_data_list = []

        try:
            table_rows = item.find_elements(By.CSS_SELECTOR, ".ivu-table-row")
            for row in table_rows:
                try:
                    department = self.extract_text_from_row(row, ["td:nth-child(1)"])
                    research_direction = self.extract_text_from_row(row, ["td:nth-child(4)"])
                    exam_data = self.extract_exam_subjects_from_row(row)
                    enrollment_plan = self.extract_enrollment_plan_from_row(row)

                    detailed_data = {
                        'department': department,
                        'research_direction': research_direction,
                        'enrollment_plan': enrollment_plan,
                        **exam_data
                    }
                    detailed_data_list.append(detailed_data)
                except Exception:
                    continue

        except Exception:
            pass

        return detailed_data_list

    def extract_text_from_row(self, row, selectors):
        """从表格行中提取文本"""
        for selector in selectors:
            try:
                element = row.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if text:
                    return text
            except:
                continue
        return ""

    def extract_exam_subjects_from_row(self, row):
        """从表格行中提取考试科目信息"""
        exam_data = {
            'politics_subject': '',
            'foreign_language_subject': '',
            'business_subject1': '',
            'business_subject2': ''
        }

        try:
            exam_buttons = row.find_elements(By.CSS_SELECTOR, "a[href*='javascript:;']")
            for button in exam_buttons:
                if "查看" in button.text:
                    try:
                        self.driver.execute_script("arguments[0].click();", button)
                        time.sleep(2)

                        popup = self.wait_for_element(By.CSS_SELECTOR, ".ivu-poptip-popper")
                        if popup:
                            self.parse_exam_popup_content(popup, exam_data)
                            self.close_popup()
                            break
                    except Exception:
                        continue

        except Exception:
            pass

        return exam_data

    def parse_exam_popup_content(self, popup, exam_data):
        """解析考试科目弹出窗口内容"""
        try:
            popup_text = popup.text
            lines = [line.strip() for line in popup_text.split('\n') if line.strip()]

            for i, line in enumerate(lines):
                if i == 0 or '思想政治' in line or '(101)' in line:
                    exam_data['politics_subject'] = line
                elif i == 1 or any(keyword in line for keyword in ['英语', '日语', '俄语', '(201)', '(202)', '(203)']):
                    exam_data['foreign_language_subject'] = line
                elif i == 2 or '业务课一' in line:
                    exam_data['business_subject1'] = line
                elif i == 3 or '业务课二' in line:
                    exam_data['business_subject2'] = line

        except Exception:
            pass

    def extract_enrollment_plan_from_row(self, row):
        """从表格行中提取拟招生人数"""
        enrollment_plan = ""

        try:
            plan_buttons = row.find_elements(By.CSS_SELECTOR, "a[href*='javascript:;']")
            for button in plan_buttons:
                if "查看" in button.text:
                    try:
                        self.driver.execute_script("arguments[0].click();", button)
                        time.sleep(4)

                        popup = self.wait_for_element(By.CSS_SELECTOR, ".ivu-tooltip-popper")
                        if popup:
                            plan_text = popup.text.strip()
                            match = re.search(r'专业：\s*(\d+)', plan_text)
                            if match:
                                enrollment_plan = f"{match.group(1)}(不含推免)"
                            else:
                                match = re.search(r'(\d+)', plan_text)
                                if match:
                                    enrollment_plan = f"{match.group(1)}(不含推免)"
                            self.close_popup()
                            break
                    except Exception:
                        continue

        except Exception:
            pass

        return enrollment_plan

    def close_popup(self):
        """关闭弹出窗口"""
        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            body.click()
            time.sleep(2)
        except:
            pass

    def extract_major_basic_info(self, item):
        """提取专业基本信息"""
        try:
            name_elem = item.find_element(By.CSS_SELECTOR, ".zy-name")
            name_text = name_elem.text.strip()

            if not name_text:
                return None

            code_match = re.search(r'\((\d+)\)', name_text)
            major_code = code_match.group(1) if code_match else ""
            major_name = re.sub(r'\(\d+\)', '', name_text).strip()

            if not major_name:
                return None

            degree_type = ""
            try:
                degree_elem = item.find_element(By.CSS_SELECTOR, ".zy-tag.xs, .zy-tag.zs")
                degree_type = degree_elem.text.strip()
            except:
                if "专业学位" in name_text:
                    degree_type = "专业学位"
                elif "学术学位" in name_text:
                    degree_type = "学术学位"
                elif major_code and major_code.startswith('085'):
                    degree_type = "专业学位"
                else:
                    degree_type = "学术学位"

            return {
                'major_name': major_name,
                'major_code': major_code,
                'degree_type': degree_type
            }
        except Exception:
            return None

    def get_major_details_from_detail_page(self, item, school_name):
        """从详情页面获取专业详细信息"""
        details = {
            'enrollment_plan': '',
            'politics_subject': '',
            'foreign_language_subject': '',
            'business_subject1': '',
            'business_subject2': ''
        }

        try:
            detail_links = item.find_elements(By.CSS_SELECTOR, "a[href*='/zsml/queryYjfx']")
            if detail_links:
                for detail_link in detail_links:
                    try:
                        detail_url = detail_link.get_attribute("href")
                        if detail_url:
                            if not detail_url.startswith('http'):
                                detail_url = 'https://yz.chsi.com.cn' + detail_url

                            original_window = self.driver.current_window_handle
                            self.driver.execute_script("window.open(arguments[0]);", detail_url)
                            time.sleep(4)

                            new_window = [w for w in self.driver.window_handles if w != original_window][0]
                            self.driver.switch_to.window(new_window)
                            time.sleep(4)

                            if "登录" not in self.driver.title and "错误" not in self.driver.title:
                                page_details = self.parse_detail_page()
                                details.update(page_details)

                            self.driver.close()
                            self.driver.switch_to.window(original_window)
                            time.sleep(3)
                            break
                    except Exception:
                        try:
                            self.driver.switch_to.window(original_window)
                        except:
                            pass
                        continue

        except Exception:
            pass

        return details

    def parse_detail_page(self):
        """解析详情页面"""
        details = {
            'enrollment_plan': '',
            'politics_subject': '',
            'foreign_language_subject': '',
            'business_subject1': '',
            'business_subject2': ''
        }

        try:
            enrollment_plan = self.extract_enrollment_plan_from_detail_page()
            if enrollment_plan:
                details['enrollment_plan'] = enrollment_plan

            exam_data = self.extract_exam_subjects_from_detail_page()
            details.update(exam_data)

        except Exception:
            pass

        return details

    def extract_enrollment_plan_from_detail_page(self):
        """从详情页面提取拟招生人数"""
        enrollment_plan = ""

        try:
            page_text = self.driver.page_source
            match = re.search(r'专业：\s*(\d+)', page_text)
            if match:
                enrollment_plan = f"{match.group(1)}(不含推免)"

        except Exception:
            pass

        return enrollment_plan

    def extract_exam_subjects_from_detail_page(self):
        """从详情页面提取考试科目信息"""
        exam_data = {
            'politics_subject': '',
            'foreign_language_subject': '',
            'business_subject1': '',
            'business_subject2': ''
        }

        try:
            kskm_items = self.driver.find_elements(By.CSS_SELECTOR, ".kskm-item")
            if kskm_items:
                first_kskm = kskm_items[0]
                kskm_details = first_kskm.find_elements(By.CSS_SELECTOR, ".kskm-detail .item")

                for i, item in enumerate(kskm_details):
                    text = item.text.strip()
                    if not text:
                        continue

                    clean_text = re.sub(r'见招生简章|查看详情', '', text).strip()

                    if i == 0:
                        exam_data['politics_subject'] = clean_text
                    elif i == 1:
                        exam_data['foreign_language_subject'] = clean_text
                    elif i == 2:
                        exam_data['business_subject1'] = clean_text
                    elif i == 3:
                        exam_data['business_subject2'] = clean_text

        except Exception:
            pass

        return exam_data

    def extract_region_from_school_page(self):
        """从学校页面提取地区信息"""
        try:
            page_text = self.driver.page_source
            region_patterns = [
                r'<div class="yx-area"[^>]*>.*?([\u4e00-\u9fa5]{2,10})</div>',
                r'所在地.*?([\u4e00-\u9fa5]{2,10})',
            ]

            for pattern in region_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    region = match.group(1)
                    return region

            return "未知"
        except Exception:
            return "未知"

    def extract_school_features_from_page(self):
        """从学校页面提取院校特性"""
        try:
            features = []
            feature_selectors = [".yx-tag", ".yx-tags .yx-tag"]

            for selector in feature_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and text not in features:
                            features.append(text)
                except:
                    continue

            return list(set(features))
        except Exception:
            return []

    def expand_all_major_details(self):
        """展开所有专业详细信息"""
        try:
            expand_buttons = self.driver.find_elements(By.CSS_SELECTOR, ".show-more, [class*='expand']")
            for button in expand_buttons:
                try:
                    if button.is_displayed() and ("展开" in button.text or "详情" in button.text):
                        self.driver.execute_script("arguments[0].click();", button)
                        time.sleep(1)
                except:
                    continue

            return True
        except Exception:
            return False

    def find_major_button(self):
        """查找开设专业按钮"""
        button_selectors = [
            "a.zy-btn.ivu-btn.ivu-btn-primary",
            "a[href*='/zsml/dwzy.do']",
            "//a[contains(text(), '开设专业')]"
        ]

        for selector in button_selectors:
            try:
                if selector.startswith("//"):
                    button = self.driver.find_element(By.XPATH, selector)
                else:
                    button = self.driver.find_element(By.CSS_SELECTOR, selector)

                if button.is_displayed():
                    return button
            except:
                continue

        return None

    def check_no_results(self):
        """检查是否没有结果"""
        try:
            no_data_indicators = ["//*[contains(text(), '暂无数据')]", "//*[contains(text(), '没有找到')]"]
            for indicator in no_data_indicators:
                try:
                    no_data = self.driver.find_element(By.XPATH, indicator)
                    if no_data and no_data.is_displayed():
                        return True
                except:
                    continue
            return False
        except:
            return False

    def close(self):
        """关闭浏览器"""
        if hasattr(self, 'driver'):
            try:
                self.driver.quit()
                logging.info(f"线程 {self.thread_id} 浏览器已关闭")
            except:
                pass


class CompleteInfoSpider:
    def __init__(self, max_workers=2):
        self.max_workers = max_workers
        self.lock = threading.Lock()
        self.excel_filename = f'完整信息_考研专业信息-{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

        self.check_and_create_tables()
        self.init_excel_file()

    def init_excel_file(self):
        """初始化Excel文件"""
        try:
            df = pd.DataFrame(columns=[
                '学校', '专业名称', '专业代码', '院系', '研究方向',
                '政治科目', '外语科目', '业务课一', '业务课二',
                '拟招生人数', '地区', '院校特性', '学位类型',
                '搜索关键词', '数据来源'
            ])
            df.to_excel(self.excel_filename, index=False, engine='openpyxl')
            logging.info(f"Excel文件已初始化: {self.excel_filename}")
        except Exception as e:
            logging.error(f"初始化Excel文件失败: {e}")

    def append_to_excel(self, data_list):
        """追加数据到Excel文件"""
        if not data_list:
            return

        with self.lock:
            try:
                try:
                    existing_df = pd.read_excel(self.excel_filename, engine='openpyxl')
                except:
                    existing_df = pd.DataFrame()

                new_data = []
                for data in data_list:
                    new_data.append({
                        '学校': data['school_name'],
                        '专业名称': data['major_name'],
                        '专业代码': data.get('major_code', ''),
                        '院系': data.get('department', ''),
                        '研究方向': data.get('research_direction', ''),
                        '政治科目': data.get('politics_subject', ''),
                        '外语科目': data.get('foreign_language_subject', ''),
                        '业务课一': data.get('business_subject1', ''),
                        '业务课二': data.get('business_subject2', ''),
                        '拟招生人数': data.get('enrollment_plan', ''),
                        '地区': data.get('region', ''),
                        '院校特性': data.get('school_features', ''),
                        '学位类型': data.get('degree_type', ''),
                        '搜索关键词': data.get('search_keyword', ''),
                        '数据来源': data['data_source']
                    })

                new_df = pd.DataFrame(new_data)

                if not existing_df.empty:
                    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                else:
                    combined_df = new_df

                combined_df.to_excel(self.excel_filename, index=False, engine='openpyxl')
                logging.info(f"已追加 {len(data_list)} 条数据到Excel文件")

            except Exception as e:
                logging.error(f"追加数据到Excel失败: {e}")

    def check_and_create_tables(self):
        """检查并创建表"""
        connection = self.get_db_connection()
        if not connection:
            return

        try:
            cursor = connection.cursor()

            cursor.execute("SHOW TABLES LIKE 'exam_subjects'")
            if not cursor.fetchone():
                cursor.execute("""
                    CREATE TABLE exam_subjects (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        school_name VARCHAR(255) NOT NULL,
                        major_name VARCHAR(255) NOT NULL,
                        major_code VARCHAR(100),
                        department VARCHAR(255),
                        research_direction VARCHAR(255),
                        politics_subject VARCHAR(100),
                        foreign_language_subject VARCHAR(100),
                        business_subject1 VARCHAR(255),
                        business_subject2 VARCHAR(255),
                        enrollment_plan VARCHAR(100),
                        region VARCHAR(100),
                        data_source VARCHAR(500) NOT NULL,
                        school_features TEXT,
                        degree_type VARCHAR(50),
                        search_type ENUM('region', 'school') DEFAULT 'region',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                logging.info("创建表 exam_subjects")

            connection.commit()
            logging.info("数据表检查完成")

        except MySQLError as e:
            logging.error(f"检查表失败: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def get_db_connection(self):
        """获取数据库连接"""
        try:
            connection = mysql.connector.connect(**DB_CONFIG)
            return connection
        except MySQLError as e:
            logging.error(f"数据库连接失败: {e}")
            return None

    def check_school_exists_in_database(self, school_name, search_type='region'):
        """检查学校是否已在数据库中存在"""
        connection = self.get_db_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            query = "SELECT COUNT(*) FROM exam_subjects WHERE school_name = %s AND search_type = %s"
            cursor.execute(query, (school_name, search_type))
            count = cursor.fetchone()[0]
            return count > 0
        except MySQLError:
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def delete_school_data(self, school_name, search_type='region'):
        """删除指定学校的数据"""
        connection = self.get_db_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            query = "DELETE FROM exam_subjects WHERE school_name = %s AND search_type = %s"
            cursor.execute(query, (school_name, search_type))
            connection.commit()
            logging.info(f"已删除学校 {school_name} 的现有数据")
            return True
        except MySQLError:
            connection.rollback()
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def ask_user_for_existing_schools(self, school_list, search_type='region'):
        """询问用户对已存在学校的处理方式"""
        schools_to_crawl = []

        for school_info in school_list:
            school_name = school_info['name']
            exists = self.check_school_exists_in_database(school_name, search_type)

            if exists:
                while True:
                    choice = input(f"学校 '{school_name}' 已存在，是否重新爬取？(y/n): ").strip().lower()
                    if choice in ['y', 'yes', '是']:
                        if self.delete_school_data(school_name, search_type):
                            schools_to_crawl.append(school_info)
                        break
                    elif choice in ['n', 'no', '否']:
                        break
            else:
                schools_to_crawl.append(school_info)

        return schools_to_crawl

    def save_to_database(self, data):
        """保存数据到数据库"""
        if not data:
            return False

        connection = self.get_db_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            saved_count = 0

            for item in data:
                try:
                    query = """
                    INSERT INTO exam_subjects 
                    (school_name, major_name, major_code, department, research_direction,
                     politics_subject, foreign_language_subject, business_subject1, business_subject2,
                     enrollment_plan, region, data_source, school_features, degree_type, search_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(query, (
                        item.get('school_name', ''),
                        item.get('major_name', ''),
                        item.get('major_code', ''),
                        item.get('department', ''),
                        item.get('research_direction', ''),
                        item.get('politics_subject', ''),
                        item.get('foreign_language_subject', ''),
                        item.get('business_subject1', ''),
                        item.get('business_subject2', ''),
                        item.get('enrollment_plan', ''),
                        item.get('region', ''),
                        item.get('data_source', ''),
                        item.get('school_features', ''),
                        item.get('degree_type', ''),
                        item.get('search_type', 'region')
                    ))
                    saved_count += 1
                except MySQLError:
                    continue

            connection.commit()
            logging.info(f"成功保存 {saved_count} 条数据到数据库")
            return True

        except MySQLError:
            connection.rollback()
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def crawl_school_task(self, school_info, region=None, search_type='region', thread_id=0):
        """单个学校的爬取任务"""
        thread_spider = ThreadSafeSpider(thread_id)
        try:
            school_name = school_info['name']
            school_data = thread_spider.crawl_school_majors(
                school_info['name'],
                school_info.get('major_link'),
                region,
                school_info.get('features', []),
                search_type
            )

            if school_data:
                self.save_to_database(school_data)
                self.append_to_excel(school_data)
                logging.info(f"线程 {thread_id} 完成学校 {school_name}，获取 {len(school_data)} 条数据")
                return school_data
            else:
                logging.info(f"线程 {thread_id} 学校 {school_name} 没有找到目标专业")
                return []

        except Exception as e:
            logging.error(f"线程 {thread_id} 处理学校 {school_info['name']} 时发生错误: {e}")
            return []
        finally:
            thread_spider.close()

    def crawl_all_schools_multithread(self, school_list, region=None, search_type='region'):
        """多线程批量爬取所有学校"""
        all_data = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_school = {
                executor.submit(self.crawl_school_task, school, region, search_type, i): (school, i)
                for i, school in enumerate(school_list)
            }

            for future in as_completed(future_to_school):
                school, thread_id = future_to_school[future]
                try:
                    school_data = future.result()
                    if school_data:
                        all_data.extend(school_data)
                except Exception as e:
                    logging.error(f"学校 {school['name']} 爬取失败: {e}")

        return all_data

    def get_available_regions(self):
        """获取所有可用地区"""
        temp_spider = ThreadSafeSpider(0)
        try:
            temp_spider.driver.get("https://yz.chsi.com.cn/zsml/dw.do")
            time.sleep(5)

            area_items = temp_spider.driver.find_elements(By.CSS_SELECTOR, ".area-item")
            all_regions = []

            for area_item in area_items:
                regions = area_item.find_elements(By.CSS_SELECTOR, ".option-item")
                for region in regions:
                    region_name = region.text.strip()
                    all_regions.append(region_name)

            return all_regions

        except Exception as e:
            logging.error(f"获取可用地区失败: {e}")
            return []
        finally:
            temp_spider.close()

    def select_region_and_features(self):
        """交互式选择地区和院校特性"""
        try:
            all_regions = self.get_available_regions()
            if not all_regions:
                return [], []

            print("\n一区:", end=" ")
            for i, region in enumerate(all_regions[:21]):
                print(f"{i + 1}.{region}", end=" ")

            print("\n\n二区:", end=" ")
            for i, region in enumerate(all_regions[21:], 22):
                print(f"{i}.{region}", end=" ")
            print()

            region_input = input("请输入编号（多个用逗号分隔，0选择所有）: ").strip()
            selected_regions = []

            if region_input == "0":
                selected_regions = all_regions
            else:
                input_nums = [num.strip() for num in region_input.split(',') if num.strip()]
                for num in input_nums:
                    if num.isdigit() and 1 <= int(num) <= len(all_regions):
                        selected_regions.append(all_regions[int(num) - 1])

            if not selected_regions:
                print("未选择任何有效地区")
                return [], []

            feature_input = input("输入院校特性编号（1.博士点 2.双一流 3.自划线，用逗号分隔，回车跳过）: ").strip()
            selected_features = []

            if feature_input:
                input_nums = [num.strip() for num in feature_input.split(',') if num.strip()]
                for num in input_nums:
                    if num == "1":
                        selected_features.append("bs")
                    elif num == "2":
                        selected_features.append("syl")
                    elif num == "3":
                        selected_features.append("zhx")

            return selected_regions, selected_features

        except Exception as e:
            logging.error(f"选择地区和特性失败: {e}")
            return [], []

    def select_schools_by_name(self):
        """按学校名称选择学校"""
        school_input = input("请输入学校名称（多个用逗号分隔）: ").strip()
        if not school_input:
            return []

        return [name.strip() for name in school_input.split(',') if name.strip()]

    def search_schools_by_region_and_features(self, region, features):
        """根据地区和特性搜索学校"""
        temp_spider = ThreadSafeSpider(0)
        try:
            temp_spider.driver.get("https://yz.chsi.com.cn/zsml/dw.do")
            time.sleep(3)

            area_items = temp_spider.driver.find_elements(By.CSS_SELECTOR, ".area-item")
            region_found = False
            for area_item in area_items:
                regions = area_item.find_elements(By.CSS_SELECTOR, ".option-item")
                for region_elem in regions:
                    if region_elem.text.strip() == region:
                        region_elem.click()
                        region_found = True
                        break
                if region_found:
                    break

            if not region_found:
                return []

            if features:
                for feature in features:
                    try:
                        checkbox = temp_spider.driver.find_element(By.CSS_SELECTOR,
                                                                   f"input[type='checkbox'][value='{feature}']")
                        if not checkbox.is_selected():
                            checkbox.click()
                    except:
                        pass

            search_button = temp_spider.wait_for_element_clickable(By.CSS_SELECTOR, "button.ivu-btn-primary")
            if search_button:
                search_button.click()
                time.sleep(3)

            schools = []
            school_items = temp_spider.driver.find_elements(By.CSS_SELECTOR, ".zy-item")
            for item in school_items:
                try:
                    name_elem = item.find_element(By.CSS_SELECTOR, ".yx-name")
                    school_name = name_elem.text.strip()
                    clean_name = re.sub(r'\(\d+\)', '', school_name).strip()

                    school_features = []
                    try:
                        feature_tags = item.find_elements(By.CSS_SELECTOR, ".yx-tag")
                        for tag in feature_tags:
                            feature_text = tag.text.strip()
                            if feature_text:
                                school_features.append(feature_text)
                    except:
                        pass

                    major_link_elem = item.find_element(By.CSS_SELECTOR, ".zy-btn")
                    major_link = major_link_elem.get_attribute("href")

                    schools.append({
                        'name': clean_name,
                        'major_link': major_link,
                        'features': school_features
                    })
                except:
                    continue

            logging.info(f"地区 {region} 找到 {len(schools)} 所学校")
            return schools

        except Exception as e:
            logging.error(f"搜索学校失败 - 地区: {region}: {e}")
            return []
        finally:
            temp_spider.close()

    def search_school_by_name(self, school_name):
        """根据学校名称搜索学校"""
        temp_spider = ThreadSafeSpider(0)
        try:
            temp_spider.driver.get("https://yz.chsi.com.cn/zsml/dw.do")
            time.sleep(3)

            school_search_input = temp_spider.wait_for_element(
                By.CSS_SELECTOR, "input[placeholder='请输入招生单位名称']"
            )
            if not school_search_input:
                return None

            school_search_input.clear()
            school_search_input.send_keys(school_name)
            time.sleep(3)

            search_button = temp_spider.wait_for_element_clickable(
                By.CSS_SELECTOR, "button.ivu-btn-primary"
            )
            if search_button:
                search_button.click()
                time.sleep(3)
            else:
                return None

            if temp_spider.check_no_results():
                return None

            school_items = temp_spider.driver.find_elements(By.CSS_SELECTOR, ".zy-item")
            if school_items:
                item = school_items[0]
                name_elem = item.find_element(By.CSS_SELECTOR, ".yx-name")
                school_name = name_elem.text.strip()
                clean_name = re.sub(r'\(\d+\)', '', school_name).strip()

                school_features = []
                try:
                    feature_tags = item.find_elements(By.CSS_SELECTOR, ".yx-tag")
                    for tag in feature_tags:
                        feature_text = tag.text.strip()
                        if feature_text:
                            school_features.append(feature_text)
                except:
                    pass

                major_link_elem = item.find_element(By.CSS_SELECTOR, ".zy-btn")
                major_link = major_link_elem.get_attribute("href")

                return {
                    'name': clean_name,
                    'major_link': major_link,
                    'features': school_features
                }
            else:
                return None

        except Exception as e:
            logging.error(f"搜索学校 {school_name} 失败: {e}")
            return None
        finally:
            temp_spider.close()

    def crawl_by_regions_and_features(self, regions, features):
        """按地区和特性爬取所有学校"""
        all_data = []

        for region in regions:
            schools = self.search_schools_by_region_and_features(region, features)
            if not schools:
                continue

            filtered_schools = self.ask_user_for_existing_schools(schools, 'region')
            if not filtered_schools:
                continue

            region_data = self.crawl_all_schools_multithread(filtered_schools, region, 'region')
            all_data.extend(region_data)
            logging.info(f"地区 {region} 爬取完成，共获取 {len(region_data)} 条专业信息")

        logging.info(f"所有地区爬取完成，共获取 {len(all_data)} 条专业信息")
        return all_data

    def crawl_by_school_names(self, school_names):
        """按学校名称爬取学校专业信息"""
        schools_to_crawl = []
        for school_name in school_names:
            school_info = self.search_school_by_name(school_name)
            if school_info:
                schools_to_crawl.append(school_info)

        if not schools_to_crawl:
            return []

        filtered_schools = self.ask_user_for_existing_schools(schools_to_crawl, 'school')
        if not filtered_schools:
            return []

        all_data = self.crawl_all_schools_multithread(filtered_schools, None, 'school')
        logging.info(f"所有学校爬取完成，共获取 {len(all_data)} 条专业信息")
        return all_data

    def delete_region_data(self, region):
        """删除指定地区的数据"""
        connection = self.get_db_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            query = "DELETE FROM exam_subjects WHERE region = %s AND search_type = 'region'"
            cursor.execute(query, (region,))
            connection.commit()
            logging.info(f"已删除地区 {region} 的所有数据")
            return True
        except MySQLError:
            connection.rollback()
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()


class ShanghaiRankingSpider:
    """软科排名爬虫类"""

    def __init__(self, headless=False):
        self.headless = headless
        self.driver = None
        self.wait = None
        self.edge_driver_path = "msedgedriver.exe"
        self.all_subjects = {}

        self.setup_driver()
        self.create_tables()

    def setup_driver(self):
        """配置Edge浏览器驱动"""
        try:
            edge_options = Options()

            if self.headless:
                edge_options.add_argument('--headless')
                edge_options.add_argument('--disable-gpu')

            edge_options.add_argument('--no-sandbox')
            edge_options.add_argument('--disable-dev-shm-usage')
            edge_options.add_argument('--window-size=1920,1080')
            edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            edge_options.add_experimental_option('useAutomationExtension', False)
            edge_options.add_argument('--disable-blink-features=AutomationControlled')

            edge_options.add_argument(
                'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
            )

            if not os.path.exists(self.edge_driver_path):
                raise FileNotFoundError(f"Edge驱动文件不存在: {self.edge_driver_path}")

            service = Service(executable_path=self.edge_driver_path)
            self.driver = webdriver.Edge(service=service, options=edge_options)

            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 10)
            self.driver.implicitly_wait(5)

            logging.info("浏览器驱动初始化成功")

        except Exception as e:
            logging.error(f"浏览器驱动初始化失败: {e}")
            raise

    def wait_for_element(self, by, value, timeout=10):
        """等待元素出现"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            return None

    def get_db_connection(self):
        """获取数据库连接"""
        try:
            connection = mysql.connector.connect(**DB_CONFIG)
            return connection
        except MySQLError as e:
            logging.error(f"数据库连接失败: {e}")
            return None

    def create_tables(self):
        """创建软科排名数据表"""
        connection = self.get_db_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            cursor.execute("SHOW TABLES LIKE 'shanghai_subject_rankings'")
            if not cursor.fetchone():
                cursor.execute("""
                    CREATE TABLE shanghai_subject_rankings (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        year INT NOT NULL,
                        subject_code VARCHAR(20) NOT NULL,
                        subject_name VARCHAR(100) NOT NULL,
                        ranking_position_2025 INT,
                        ranking_position_2024 INT,
                        school_name VARCHAR(255) NOT NULL,
                        score_2025 FLOAT,
                        score_2024 FLOAT,
                        subject_category VARCHAR(50),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                connection.commit()
                logging.info("软科排名数据表创建成功")
                return True
        except MySQLError as e:
            logging.error(f"创建软科排名表失败: {e}")
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def fetch_all_subjects_from_web(self):
        """从软科排名页面动态爬取所有学科信息"""
        try:
            self.driver.get("https://www.shanghairanking.cn/rankings/bcsr/2025")
            time.sleep(5)

            # 等待页面加载
            self.wait_for_element(By.CLASS_NAME, "subject-item", timeout=15)

            subject_items = self.driver.find_elements(By.CLASS_NAME, "subject-item")
            all_subjects = {}

            for item in subject_items:
                try:
                    # 获取类别ID和名称
                    category_code = item.get_attribute("id")
                    if not category_code:
                        continue

                    # 获取类别标题
                    category_title_elem = item.find_element(By.CSS_SELECTOR, ".subject-category .subject-title")
                    category_name = category_title_elem.text.strip() if category_title_elem else f"类别{category_code}"

                    # 获取学科列表
                    subject_list = item.find_element(By.CLASS_NAME, "subject-list")
                    subject_links = subject_list.find_elements(By.CLASS_NAME, "subj-link")

                    subjects_in_category = []
                    for link in subject_links:
                        try:
                            spans = link.find_elements(By.TAG_NAME, "span")
                            if len(spans) >= 2:
                                subject_code = spans[0].text.strip()
                                subject_name = spans[1].text.strip()
                                if subject_code and subject_name:
                                    subjects_in_category.append((subject_code, subject_name))
                        except Exception:
                            continue

                    if subjects_in_category:
                        all_subjects[category_code] = {
                            'category_name': category_name,
                            'subjects': subjects_in_category
                        }

                except Exception as e:
                    logging.error(f"解析类别失败: {e}")
                    continue

            self.all_subjects = all_subjects
            return all_subjects

        except Exception as e:
            logging.error(f"爬取学科信息失败: {e}")
            return {}

    def display_all_subjects(self):
        """显示所有爬取到的学科信息"""
        if not self.all_subjects:
            self.fetch_all_subjects_from_web()

        if not self.all_subjects:
            print("未能获取到学科信息")
            return {}

        subject_mapping = {}
        subject_index = 1

        # 先打印所有学科
        print("\n=== 可用学科列表 ===")

        sorted_categories = sorted(self.all_subjects.items(), key=lambda x: x[0])
        for category_code, category_info in sorted_categories:
            print(f"\n{category_info['category_name']} ({category_code}):")

            for subject_code, subject_name in category_info['subjects']:
                print(f"  {subject_index:3d}. {subject_code} {subject_name}")
                subject_mapping[subject_index] = (
                    subject_code, subject_name, category_code, category_info['category_name']
                )
                subject_index += 1

        print(f"\n共计 {subject_index - 1} 个学科")
        return subject_mapping

    def clean_school_name(self, school_name):
        """清理学校名称"""
        if not school_name:
            return ""

        school_name = school_name.strip()
        school_name = re.sub(r'\([^)]*\)', '', school_name)
        school_name = re.sub(r'（[^）]*）', '', school_name)
        school_name = re.sub(r'\s+', ' ', school_name).strip()

        replacements = {
            '北京协和医学院(清华大学医学部)': '北京协和医学院',
            '国防科技大学（原国防科学技术大学）': '国防科技大学',
            '北京大学医学部': '北京大学',
            '复旦大学上海医学院': '复旦大学',
            '上海交通大学医学院': '上海交通大学',
        }

        for old, new in replacements.items():
            if old in school_name:
                school_name = school_name.replace(old, new)

        return school_name

    def extract_rank_number(self, rank_text):
        """从排名文本中提取排名数字"""
        if not rank_text:
            return 0

        rank_text = str(rank_text).strip()
        if rank_text.isdigit():
            return int(rank_text)
        elif '-' in rank_text:
            parts = rank_text.split('-')
            if parts[0].strip().isdigit():
                return int(parts[0].strip())
        else:
            match = re.search(r'(\d+)', rank_text)
            if match:
                return int(match.group(1))

        return 0

    def extract_score(self, score_text):
        """从分数文本中提取分数"""
        if not score_text:
            return 0.0

        try:
            cleaned_text = re.sub(r'[^\d.]', '', str(score_text))
            if cleaned_text:
                return float(cleaned_text)
            return 0.0
        except:
            return 0.0

    def navigate_to_subject_page(self, subject_code):
        """导航到学科页面"""
        url = f"https://www.shanghairanking.cn/rankings/bcsr/2025/{subject_code}"

        try:
            self.driver.get(url)
            time.sleep(3)
            table = self.wait_for_element(By.CLASS_NAME, "rk-table", timeout=20)
            return table is not None
        except Exception:
            return False

    def get_total_pages(self):
        """获取总页数"""
        try:
            pagination = self.wait_for_element(By.CLASS_NAME, "ant-pagination", timeout=15)
            if not pagination:
                return 1

            try:
                total_text_element = pagination.find_element(By.CLASS_NAME, "ant-pagination-total-text")
                text = total_text_element.text
                match = re.search(r'共\s*(\d+)\s*条', text)
                if match:
                    total_items = int(match.group(1))
                    total_pages = (total_items + 29) // 30
                    return total_pages
            except:
                pass

            return 1
        except Exception:
            return 1

    def parse_current_page(self, subject_code, subject_name, page_num=1):
        """解析当前页面的数据"""
        try:
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            table = soup.find('table', class_='rk-table')
            if not table:
                return []

            tbody = table.find('tbody')
            if not tbody:
                return []

            rows = tbody.find_all('tr')
            data_rows = []

            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 5:
                    continue

                try:
                    rank_2025 = 0
                    if len(cells) > 0:
                        rank_cell = cells[0]
                        rank_div = rank_cell.find('div', class_='ranking')
                        if rank_div:
                            rank_text = rank_div.get_text(strip=True)
                        else:
                            rank_text = rank_cell.get_text(strip=True)
                        rank_2025 = self.extract_rank_number(rank_text)

                    rank_2024 = 0
                    if len(cells) > 1:
                        rank_cell = cells[1]
                        rank_span = rank_cell.find('span')
                        if rank_span:
                            rank_text = rank_span.get_text(strip=True)
                        else:
                            rank_text = rank_cell.get_text(strip=True)
                        rank_2024 = self.extract_rank_number(rank_text)

                    school_name = ""
                    if len(cells) > 3:
                        school_cell = cells[3]
                        name_span = school_cell.find('span', class_='name-cn')
                        if name_span:
                            school_name = self.clean_school_name(name_span.get_text(strip=True))
                        else:
                            school_name = self.clean_school_name(school_cell.get_text(strip=True))

                    if not school_name or len(school_name) < 2:
                        continue

                    score_2025 = 0.0
                    if len(cells) > 4:
                        score_text = cells[4].get_text(strip=True)
                        score_2025 = self.extract_score(score_text)

                    score_2024 = 0.0

                    subject_category = ""
                    if subject_code.startswith('01'):
                        subject_category = "哲学"
                    elif subject_code.startswith('02'):
                        subject_category = "经济学"
                    elif subject_code.startswith('03'):
                        subject_category = "法学"
                    elif subject_code.startswith('04'):
                        subject_category = "教育学"
                    elif subject_code.startswith('05'):
                        subject_category = "文学"
                    elif subject_code.startswith('06'):
                        subject_category = "历史学"
                    elif subject_code.startswith('07'):
                        subject_category = "理学"
                    elif subject_code.startswith('08'):
                        subject_category = "工学"
                    elif subject_code.startswith('09'):
                        subject_category = "农学"
                    elif subject_code.startswith('10'):
                        subject_category = "医学"
                    elif subject_code.startswith('12'):
                        subject_category = "管理学"
                    elif subject_code.startswith('13'):
                        subject_category = "艺术学"
                    elif subject_code.startswith('14'):
                        subject_category = "交叉学科"
                    else:
                        subject_category = "其他"

                    data_rows.append({
                        'year': 2025,
                        'subject_code': subject_code,
                        'subject_name': subject_name,
                        'ranking_position_2025': rank_2025,
                        'ranking_position_2024': rank_2024,
                        'school_name': school_name,
                        'score_2025': score_2025,
                        'score_2024': score_2024,
                        'subject_category': subject_category,
                        'page_number': page_num
                    })

                except Exception:
                    continue

            return data_rows

        except Exception:
            return []

    def fetch_subject_data(self, subject_code, subject_name, max_pages=None):
        """获取学科所有页面数据"""
        all_data = []

        try:
            if not self.navigate_to_subject_page(subject_code):
                return []

            total_pages = self.get_total_pages()
            if max_pages and max_pages < total_pages:
                total_pages = max_pages

            for page_num in range(1, total_pages + 1):
                try:
                    if page_num > 1:
                        self.driver.get(
                            f"https://www.shanghairanking.cn/rankings/bcsr/2025/{subject_code}?page={page_num}")
                        time.sleep(3)

                    page_data = self.parse_current_page(subject_code, subject_name, page_num)
                    if page_data:
                        all_data.extend(page_data)

                    if page_num < total_pages:
                        time.sleep(random.uniform(3, 6))

                except Exception:
                    continue

            unique_data = {}
            for data in all_data:
                key = f"{data['ranking_position_2025']}_{data['school_name']}"
                if key not in unique_data:
                    unique_data[key] = data

            all_data = list(unique_data.values())
            all_data.sort(key=lambda x: x['ranking_position_2025'])
            return all_data

        except Exception:
            return []

    def save_subject_rankings_to_db(self, rankings):
        """保存学科排名数据到数据库"""
        if not rankings:
            return False

        connection = self.get_db_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()
            saved_count = 0

            for ranking in rankings:
                try:
                    if not ranking.get('school_name') or len(ranking['school_name']) < 2:
                        continue

                    query = """
                    INSERT INTO shanghai_subject_rankings 
                    (year, subject_code, subject_name, ranking_position_2025, ranking_position_2024, 
                     school_name, score_2025, score_2024, subject_category)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    ranking_position_2025 = VALUES(ranking_position_2025),
                    ranking_position_2024 = VALUES(ranking_position_2024),
                    score_2025 = VALUES(score_2025),
                    score_2024 = VALUES(score_2024),
                    subject_category = VALUES(subject_category)
                    """

                    cursor.execute(query, (
                        ranking['year'],
                        ranking['subject_code'],
                        ranking['subject_name'],
                        ranking['ranking_position_2025'],
                        ranking['ranking_position_2024'],
                        ranking['school_name'],
                        ranking['score_2025'],
                        ranking['score_2024'],
                        ranking['subject_category']
                    ))
                    saved_count += 1

                except MySQLError:
                    continue

            connection.commit()
            logging.info(f"成功保存 {saved_count} 条数据到数据库")
            return True

        except MySQLError:
            connection.rollback()
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def close_driver(self):
        """关闭WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
                logging.info("WebDriver已关闭")
            except:
                pass


def get_db_connection():
    """获取数据库连接"""
    try:
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='your_password',
            database='kaoyan_data',
            charset='utf8mb4',
            cursorclass=DictCursor
        )
        return connection
    except pymysql.Error as e:
        st.error(f"数据库连接失败: {e}")
        return None


def init_database():
    """初始化数据库表"""
    connection = get_db_connection()
    if not connection:
        return False

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP NULL,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)

        connection.commit()
        return True
    except pymysql.Error as e:
        st.error(f"数据库初始化失败: {e}")
        return False
    finally:
        connection.close()


def hash_password(password):
    """密码哈希处理"""
    return hashlib.sha256(password.encode()).hexdigest()


def validate_email(email):
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_username(username):
    """验证用户名格式"""
    return len(username) >= 3 and len(username) <= 50 and re.match(r'^[a-zA-Z0-9_]+$', username)


def register_user(username, email, password):
    """注册新用户"""
    connection = get_db_connection()
    if not connection:
        return False, "数据库连接失败"

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                return False, "用户名已存在"

            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                return False, "邮箱已被注册"

            password_hash = hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                (username, email, password_hash)
            )

        connection.commit()
        return True, "注册成功"

    except pymysql.Error as e:
        return False, f"注册失败: {str(e)}"
    finally:
        connection.close()


def verify_user(username, password):
    """验证用户登录"""
    connection = get_db_connection()
    if not connection:
        return False, None

    try:
        with connection.cursor() as cursor:
            password_hash = hash_password(password)

            cursor.execute(
                "SELECT id, username, email FROM users WHERE username = %s AND password_hash = %s AND is_active = TRUE",
                (username, password_hash)
            )

            user = cursor.fetchone()
            if user:
                cursor.execute(
                    "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s",
                    (user['id'],)
                )
                connection.commit()
                return True, user
            else:
                return False, None

    except pymysql.Error:
        return False, None
    finally:
        connection.close()


def verify_user_by_email(email, password):
    """通过邮箱验证用户登录"""
    connection = get_db_connection()
    if not connection:
        return False, None

    try:
        with connection.cursor() as cursor:
            password_hash = hash_password(password)

            cursor.execute(
                "SELECT id, username, email FROM users WHERE email = %s AND password_hash = %s AND is_active = TRUE",
                (email, password_hash)
            )

            user = cursor.fetchone()
            if user:
                cursor.execute(
                    "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s",
                    (user['id'],)
                )
                connection.commit()
                return True, user
            else:
                return False, None

    except pymysql.Error:
        return False, None
    finally:
        connection.close()


def save_chat_history(user_id, question, answer):
    """保存聊天记录到数据库"""
    connection = get_db_connection()
    if not connection:
        return False

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO chat_history (user_id, question, answer) VALUES (%s, %s, %s)",
                (user_id, question, answer)
            )
        connection.commit()
        return True
    except pymysql.Error:
        return False
    finally:
        connection.close()


def get_chat_history(user_id, limit=10):
    """获取用户聊天记录"""
    connection = get_db_connection()
    if not connection:
        return []

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT question, answer, timestamp FROM chat_history WHERE user_id = %s ORDER BY timestamp DESC LIMIT %s",
                (user_id, limit)
            )
            return cursor.fetchall()
    except pymysql.Error:
        return []
    finally:
        connection.close()


def clear_chat_history(user_id):
    """清空用户的聊天历史记录"""
    connection = get_db_connection()
    if not connection:
        return False

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM chat_history WHERE user_id = %s",
                (user_id,)
            )
        connection.commit()
        return True
    except pymysql.Error:
        return False
    finally:
        connection.close()


def query_database(question):
    """根据问题查询考研数据库"""
    connection = get_db_connection()
    if not connection:
        return []

    try:
        with connection.cursor() as cursor:
            question_lower = question.lower()
            conditions = []
            params = []

            school_pattern = r'([\u4e00-\u9fa5]+大学)'
            school_matches = re.findall(school_pattern, question)
            if school_matches:
                for school in school_matches:
                    conditions.append("school_name LIKE %s")
                    params.append(f"%{school}%")

            major_patterns = [
                '信息安全', '计算机', '软件', '人工智能', '电子信息',
                '计算机科学与技术', '软件工程', '人工智能', '网络安全'
            ]

            for pattern in major_patterns:
                if pattern in question:
                    conditions.append("major_name LIKE %s")
                    params.append(f"%{pattern}%")

            if conditions:
                query = """
                SELECT DISTINCT 
                    school_name, major_name, major_code, department, research_direction,
                    politics_subject, foreign_language_subject, business_subject1, business_subject2,
                    enrollment_plan, region, data_source
                FROM exam_subjects 
                WHERE """ + " OR ".join(conditions) + """
                ORDER BY school_name, major_name, research_direction
                """
                cursor.execute(query, params)
            else:
                words = question.replace('?', '').replace('？', '').split()
                if len(words) > 0:
                    query = """
                    SELECT * FROM exam_subjects 
                    WHERE CONCAT(school_name, major_name, research_direction) LIKE %s
                    ORDER BY school_name, major_name
                    LIMIT 10
                    """
                    search_term = f"%{'%'.join(words)}%"
                    cursor.execute(query, (search_term,))
                else:
                    return []

            results = cursor.fetchall()
            return results

    except pymysql.Error as e:
        print(f"数据库查询错误: {e}")
        return []
    finally:
        connection.close()


def format_database_results(results):
    """格式化数据库查询结果"""
    if not results:
        return "未在数据库中查询到相关信息。"

    formatted = "以下是数据库中的相关考研信息：\n\n"

    for i, result in enumerate(results, 1):
        formatted += f"**{i}. {result['school_name']} - {result['major_name']}**"

        if result.get('major_code'):
            formatted += f"（{result['major_code']}）"
        formatted += "\n"

        if result.get('research_direction'):
            formatted += f"   **研究方向**：{result['research_direction']}\n"

        if result.get('department'):
            formatted += f"   **开设院系**：{result['department']}\n"

        if result.get('enrollment_plan'):
            formatted += f"   **拟招生人数**：{result['enrollment_plan']}\n"

        has_exam_subjects = (
                result.get('politics_subject') or
                result.get('foreign_language_subject') or
                result.get('business_subject1') or
                result.get('business_subject2')
        )

        if has_exam_subjects:
            formatted += "   **考试科目**：\n"
            if result.get('politics_subject'):
                formatted += f"   - 政治：{result['politics_subject']}\n"
            if result.get('foreign_language_subject'):
                formatted += f"   - 外语：{result['foreign_language_subject']}\n"
            if result.get('business_subject1'):
                formatted += f"   - 业务课一：{result['business_subject1']}\n"
            if result.get('business_subject2'):
                formatted += f"   - 业务课二：{result['business_subject2']}\n"

        formatted += f"   **地区**：{result.get('region', '未记录')}\n"
        formatted += "\n"

    formatted += """
---
**重要说明**：以上信息基于数据库中的历史招生数据，实际招生信息请以学校官方最新公布为准。
"""
    return formatted


def query_shanghai_ranking(question):
    """查询软科排名数据"""
    connection = get_db_connection()
    if not connection:
        return []

    try:
        with connection.cursor() as cursor:
            question_lower = question.lower()

            ranking_keywords = ['排名', '软科', '学科评估', '学科排名']
            if not any(keyword in question_lower for keyword in ranking_keywords):
                return []

            subject_keywords = {
                '数学': ['数学', 'math'],
                '计算机': ['计算机', '软件', '人工智能', 'ai', 'computer'],
                '物理学': ['物理'],
                '化学': ['化学'],
                '生物学': ['生物'],
                '统计学': ['统计'],
                '机械工程': ['机械'],
                '电子信息': ['电子', '通信', '信息']
            }

            conditions = []
            params = []

            for subject_name, keywords in subject_keywords.items():
                for keyword in keywords:
                    if keyword in question_lower:
                        conditions.append("subject_name LIKE %s")
                        params.append(f"%{subject_name}%")
                        break

            school_pattern = r'([\u4e00-\u9fa5]+大学)'
            school_matches = re.findall(school_pattern, question)
            if school_matches:
                for school in school_matches:
                    conditions.append("school_name LIKE %s")
                    params.append(f"%{school}%")

            if conditions:
                query = """
                SELECT 
                    subject_name, school_name, ranking_position_2025, ranking_position_2024,
                    score_2025, score_2024, subject_category
                FROM shanghai_subject_rankings 
                WHERE """ + " OR ".join(conditions)

                if '前十' in question or '前10' in question:
                    query += " AND ranking_position_2025 <= 10 ORDER BY ranking_position_2025"
                elif '前二十' in question or '前20' in question:
                    query += " AND ranking_position_2025 <= 20 ORDER BY ranking_position_2025"
                elif '前五十' in question or '前50' in question:
                    query += " AND ranking_position_2025 <= 50 ORDER BY ranking_position_2025"
                else:
                    query += " ORDER BY subject_name, ranking_position_2025"

                cursor.execute(query, params)
            else:
                query = """
                SELECT 
                    subject_name, school_name, ranking_position_2025, ranking_position_2024,
                    score_2025, score_2024, subject_category
                FROM shanghai_subject_rankings 
                WHERE ranking_position_2025 <= 50
                ORDER BY subject_name, ranking_position_2025
                """
                cursor.execute(query)

            results = cursor.fetchall()
            return results

    except pymysql.Error as e:
        print(f"软科排名查询错误: {e}")
        return []
    finally:
        connection.close()


def format_shanghai_ranking_results(results):
    """格式化软科排名查询结果"""
    if not results:
        return "未在软科排名数据库中查询到相关信息。"

    grouped_results = {}
    for result in results:
        subject_name = result['subject_name']
        if subject_name not in grouped_results:
            grouped_results[subject_name] = []
        grouped_results[subject_name].append(result)

    formatted = "**软科2025学科排名信息：**\n\n"

    for subject_name, rankings in grouped_results.items():
        formatted += f"**{subject_name}**\n"

        max_display = 20
        for i, ranking in enumerate(rankings[:max_display]):
            formatted += f"{i + 1:2d}. {ranking['school_name']:<20s} "
            formatted += f"排名2025: {ranking['ranking_position_2025']:3d} "

            if ranking['ranking_position_2024'] > 0:
                formatted += f"排名2024: {ranking['ranking_position_2024']:3d} "

            if ranking['score_2025'] > 0:
                formatted += f"分数: {ranking['score_2025']:.1f}"

            formatted += "\n"

        if len(rankings) > max_display:
            formatted += f"  ... 还有 {len(rankings) - max_display} 所学校\n"

        formatted += "\n"

    formatted += """
---
**说明**：排名基于软科2025年中国大学学科排名，数据来源：https://www.shanghairanking.cn/
"""
    return formatted


def combine_query_results(question):
    """合并考试科目和排名查询结果"""
    exam_results = query_database(question)
    exam_context = format_database_results(exam_results)

    ranking_results = query_shanghai_ranking(question)
    ranking_context = format_shanghai_ranking_results(ranking_results)

    combined_context = ""

    if "未在数据库中查询到相关信息" not in exam_context:
        combined_context += f"**考研专业信息：**\n{exam_context}\n\n"

    if "未在软科排名数据库中查询到相关信息" not in ranking_context:
        combined_context += f"**软科排名信息：**\n{ranking_context}"

    if not combined_context:
        combined_context = "抱歉，未在数据库中查询到相关信息。"

    return combined_context


def call_deepseek_api(question, context):
    """调用DeepSeek API"""
    try:
        api_key = st.secrets.get("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
        url = "https://api.deepseek.com/v1/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        system_prompt = """你是一个专业的考研咨询助手，请严格按照提供的数据库信息回答问题。"""

        user_message = f"""用户问题：{question}

数据库查询结果：
{context}

请根据以上数据库信息回答用户问题。"""

        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.3,
            "max_tokens": 2000
        }

        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            answer = result['choices'][0]['message']['content']
            return answer
        else:
            return f"AI服务暂时不可用\n\n数据库查询结果：\n{context}"

    except Exception as e:
        return f"调用AI服务时出错\n\n数据库查询结果：\n{context}"


def get_school_list():
    """获取学校列表"""
    connection = get_db_connection()
    if not connection:
        return []

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT DISTINCT school_name FROM exam_subjects ORDER BY school_name")
            schools = [row['school_name'] for row in cursor.fetchall()]
            return schools
    except pymysql.Error:
        return []
    finally:
        connection.close()


def login_page():
    """登录页面"""
    st.title("🎓 考研AI问答系统 - 登录")

    with st.form("login_form"):
        email = st.text_input("邮箱", placeholder="请输入注册邮箱")
        password = st.text_input("密码", type="password", placeholder="请输入密码")
        submit = st.form_submit_button("登录", type="primary")

        if submit:
            if not email or not password:
                st.error("请输入邮箱和密码")
            elif not validate_email(email):
                st.error("邮箱格式不正确")
            else:
                success, user = verify_user_by_email(email, password)
                if success:
                    st.session_state.user = user
                    st.session_state.page = "main"
                    st.success(f"登录成功，欢迎 {user['username']}！")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("邮箱或密码错误")

    st.markdown("---")
    if st.button("立即注册"):
        st.session_state.page = "register"
        st.rerun()


def register_page():
    """注册页面"""
    st.title("🎓 考研AI问答系统 - 注册")

    with st.form("register_form"):
        username = st.text_input("用户名", placeholder="3-50个字符，只能包含字母、数字和下划线")
        email = st.text_input("邮箱", placeholder="请输入有效的邮箱地址")
        password = st.text_input("密码", type="password", placeholder="请输入密码")
        confirm_password = st.text_input("确认密码", type="password", placeholder="请再次输入密码")
        submit = st.form_submit_button("注册")

        if submit:
            if not username or not email or not password:
                st.error("请填写所有字段")
            elif not validate_username(username):
                st.error("用户名格式不正确")
            elif not validate_email(email):
                st.error("邮箱格式不正确")
            elif password != confirm_password:
                st.error("两次输入的密码不一致")
            elif len(password) < 6:
                st.error("密码长度至少6位")
            else:
                success, message = register_user(username, email, password)
                if success:
                    st.success(message)
                else:
                    st.error(message)

    st.markdown("---")
    if st.button("返回登录"):
        st.session_state.page = "login"
        st.rerun()


def main_page():
    """主页面 - AI问答"""
    st.title("🤖 考研AI智能问答")

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.write(f"欢迎，**{st.session_state.user['username']}**！")
    with col2:
        if st.button("📊 数据查询"):
            st.session_state.page = "data_query"
            st.rerun()
    with col3:
        if st.button("🚪 退出登录"):
            st.session_state.clear()
            st.rerun()

    st.markdown("---")

    if 'show_clear_confirm' not in st.session_state:
        st.session_state.show_clear_confirm = False

    if 'messages' not in st.session_state:
        st.session_state.messages = []
        history = get_chat_history(st.session_state.user['id'])
        for item in history:
            st.session_state.messages.append({"role": "user", "content": item['question']})
            st.session_state.messages.append({"role": "assistant", "content": item['answer']})

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    st.subheader("💡 示例问题：")
    examples = [
        "中国地质大学信息安全专业有哪些研究方向？",
        "浙江大学计算机科学与技术专业的考试科目是什么？",
        "软科数学专业排名前十的学校有哪些？",
        "计算机科学与技术的软科排名情况如何？"
    ]

    cols = st.columns(4)
    for i, example in enumerate(examples):
        with cols[i]:
            if st.button(example[:15] + "..." if len(example) > 15 else example, key=f"example_{i}"):
                st.session_state.new_question = example

    question = st.text_area(
        "请输入您的问题：",
        value=st.session_state.get('new_question', ''),
        height=100,
        placeholder="例如：中国地质大学信息安全专业有哪些研究方向？或：软科数学排名前十的学校？"
    )

    col1, col2, col3 = st.columns([4, 1, 1])
    with col1:
        if st.button("🔍 获取答案", type="primary", use_container_width=True):
            if question:
                st.session_state.messages.append({"role": "user", "content": question})

                with st.chat_message("user"):
                    st.markdown(question)

                with st.chat_message("assistant"):
                    with st.spinner("正在查询数据库并生成回答..."):
                        context = combine_query_results(question)
                        response = call_deepseek_api(question, context)
                        st.markdown(response)
                        save_chat_history(st.session_state.user['id'], question, response)

                st.session_state.messages.append({"role": "assistant", "content": response})

                if 'new_question' in st.session_state:
                    del st.session_state.new_question
            else:
                st.warning("请输入问题")
    with col2:
        if st.button("清空当前对话", use_container_width=True):
            st.session_state.messages = []
            st.success("当前对话已清空")
            st.rerun()
    with col3:
        if st.button("清空历史记录", use_container_width=True):
            st.session_state.show_clear_confirm = True

    if st.session_state.show_clear_confirm:
        st.warning("⚠️ 确定要永久删除所有历史记录吗？此操作不可撤销！")
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("确定删除", type="primary"):
                if clear_chat_history(st.session_state.user['id']):
                    st.session_state.messages = []
                    st.session_state.show_clear_confirm = False
                    st.success("所有历史记录已永久删除")
                    st.rerun()
        with col_no:
            if st.button("取消"):
                st.session_state.show_clear_confirm = False
                st.rerun()


def data_query_page():
    """数据查询页面 - 四个选项卡界面"""
    st.title("📚 考研数据查询")

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.write(f"欢迎，**{st.session_state.user['username']}**！")
    with col2:
        if st.button("🤖 AI问答"):
            st.session_state.page = "main"
            st.rerun()
    with col3:
        if st.button("🚪 退出登录"):
            st.session_state.clear()
            st.rerun()

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs(["🔍 条件查询", "🏫 学校浏览", "📊 数据统计", "🥇 软科排名"])

    with tab1:
        st.subheader("条件查询")
        col1, col2 = st.columns(2)
        with col1:
            school_name = st.text_input("学校名称", key="query_school")
        with col2:
            major_name = st.text_input("专业名称", key="query_major")

        if st.button("查询", key="query_btn"):
            if school_name or major_name:
                connection = get_db_connection()
                if connection:
                    try:
                        with connection.cursor() as cursor:
                            query = "SELECT * FROM exam_subjects WHERE 1=1"
                            params = []

                            if school_name:
                                query += " AND school_name LIKE %s"
                                params.append(f"%{school_name}%")
                            if major_name:
                                query += " AND major_name LIKE %s"
                                params.append(f"%{major_name}%")

                            query += " ORDER BY school_name, major_name LIMIT 50"
                            cursor.execute(query, params)
                            results = cursor.fetchall()

                            if results:
                                st.subheader(f"找到 {len(results)} 条结果")
                                for result in results:
                                    with st.expander(f"{result['school_name']} - {result['major_name']}"):
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            st.write("**基本信息**")
                                            st.write(f"专业代码：{result.get('major_code', '')}")
                                            st.write(f"院系：{result.get('department', '')}")
                                            st.write(f"研究方向：{result.get('research_direction', '')}")
                                            st.write(f"招生人数：{result.get('enrollment_plan', '')}")
                                            st.write(f"地区：{result.get('region', '')}")

                                        with col2:
                                            st.write("**考试科目**")
                                            if result.get('politics_subject'):
                                                st.write(f"政治：{result['politics_subject']}")
                                            if result.get('foreign_language_subject'):
                                                st.write(f"外语：{result['foreign_language_subject']}")
                                            if result.get('business_subject1'):
                                                st.write(f"业务课一：{result['business_subject1']}")
                                            if result.get('business_subject2'):
                                                st.write(f"业务课二：{result['business_subject2']}")
                            else:
                                st.warning("未找到相关数据")

                    except pymysql.Error as e:
                        st.error(f"查询失败: {e}")
                    finally:
                        connection.close()
            else:
                st.warning("请输入至少一个查询条件")

    with tab2:
        st.subheader("学校专业浏览")
        schools = get_school_list()

        if schools:
            selected_school = st.selectbox("选择学校", schools, key="browse_school")

            if selected_school:
                connection = get_db_connection()
                if connection:
                    try:
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "SELECT DISTINCT major_name FROM exam_subjects WHERE school_name = %s ORDER BY major_name",
                                (selected_school,)
                            )
                            majors = [row['major_name'] for row in cursor.fetchall()]

                            if majors:
                                selected_major = st.selectbox("选择专业", majors, key="browse_major")

                                if selected_major:
                                    cursor.execute(
                                        "SELECT * FROM exam_subjects WHERE school_name = %s AND major_name = %s ORDER BY department",
                                        (selected_school, selected_major)
                                    )
                                    results = cursor.fetchall()

                                    if results:
                                        for result in results:
                                            with st.expander(
                                                    f"{result['department']} - {result.get('research_direction', '不区分研究方向')}"):
                                                col1, col2 = st.columns(2)
                                                with col1:
                                                    st.write("**基本信息**")
                                                    st.write(f"专业代码：{result.get('major_code', '')}")
                                                    st.write(f"招生人数：{result.get('enrollment_plan', '')}")

                                                with col2:
                                                    st.write("**考试科目**")
                                                    if result.get('politics_subject'):
                                                        st.write(f"政治：{result['politics_subject']}")
                                                    if result.get('foreign_language_subject'):
                                                        st.write(f"外语：{result['foreign_language_subject']}")
                                                    if result.get('business_subject1'):
                                                        st.write(f"业务课一：{result['business_subject1']}")
                                                    if result.get('business_subject2'):
                                                        st.write(f"业务课二：{result['business_subject2']}")
                            else:
                                st.warning("该学校暂无专业信息")

                    except pymysql.Error as e:
                        st.error(f"查询失败: {e}")
                    finally:
                        connection.close()
        else:
            st.warning("暂无学校数据")

    with tab3:
        st.subheader("数据统计")
        connection = get_db_connection()
        if connection:
            try:
                with connection.cursor() as cursor:
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        cursor.execute("SELECT COUNT(*) FROM exam_subjects")
                        total_records = cursor.fetchone()['COUNT(*)']
                        st.metric("总记录数", total_records)

                    with col2:
                        cursor.execute("SELECT COUNT(DISTINCT school_name) FROM exam_subjects")
                        total_schools = cursor.fetchone()['COUNT(DISTINCT school_name)']
                        st.metric("覆盖高校数", total_schools)

                    with col3:
                        cursor.execute("SELECT COUNT(DISTINCT major_name) FROM exam_subjects")
                        total_majors = cursor.fetchone()['COUNT(DISTINCT major_name)']
                        st.metric("专业数量", total_majors)

                    st.subheader("热门专业TOP 10")
                    cursor.execute("""
                        SELECT major_name, COUNT(*) as count 
                        FROM exam_subjects 
                        GROUP BY major_name 
                        ORDER BY count DESC 
                        LIMIT 10
                    """)
                    major_stats = cursor.fetchall()

                    if major_stats:
                        df_major = pd.DataFrame(major_stats)
                        st.dataframe(df_major, use_container_width=True)

                    st.subheader("地区分布")
                    cursor.execute(
                        "SELECT region, COUNT(*) as count FROM exam_subjects GROUP BY region ORDER BY count DESC")
                    region_stats = cursor.fetchall()

                    if region_stats:
                        df_region = pd.DataFrame(region_stats)
                        st.bar_chart(df_region.set_index('region'))

            except pymysql.Error as e:
                st.error(f"获取统计信息失败: {e}")
            finally:
                connection.close()

    with tab4:
        st.subheader("软科排名查询")

        col1, col2 = st.columns(2)
        with col1:
            ranking_subject = st.text_input("学科名称（如：数学、计算机）", key="ranking_subject")
        with col2:
            ranking_school = st.text_input("学校名称", key="ranking_school")

        col3, col4 = st.columns(2)
        with col3:
            top_n = st.selectbox("显示前N名", [10, 20, 50, 100, 200], index=0)
        with col4:
            subject_category = st.selectbox("学科类别", ["全部", "理学", "工学", "其他"], index=0)

        if st.button("查询排名", key="query_ranking"):
            connection = get_db_connection()
            if connection:
                try:
                    with connection.cursor() as cursor:
                        query = """
                        SELECT 
                            subject_name, school_name, ranking_position_2025, ranking_position_2024,
                            score_2025, score_2024, subject_category
                        FROM shanghai_subject_rankings 
                        WHERE 1=1
                        """
                        params = []

                        if ranking_subject:
                            query += " AND subject_name LIKE %s"
                            params.append(f"%{ranking_subject}%")

                        if ranking_school:
                            query += " AND school_name LIKE %s"
                            params.append(f"%{ranking_school}%")

                        if subject_category != "全部":
                            query += " AND subject_category = %s"
                            params.append(subject_category)

                        query += f" AND ranking_position_2025 <= {top_n}"
                        query += " ORDER BY subject_name, ranking_position_2025"

                        cursor.execute(query, params)
                        results = cursor.fetchall()

                        if results:
                            grouped_results = {}
                            for result in results:
                                subject_name = result['subject_name']
                                if subject_name not in grouped_results:
                                    grouped_results[subject_name] = []
                                grouped_results[subject_name].append(result)

                            for subject_name, rankings in grouped_results.items():
                                st.subheader(f"{subject_name}")

                                df = pd.DataFrame(rankings)
                                df = df[['school_name', 'ranking_position_2025', 'ranking_position_2024', 'score_2025',
                                         'subject_category']]
                                df.columns = ['学校名称', '2025排名', '2024排名', '2025分数', '学科类别']

                                st.dataframe(df, use_container_width=True)

                                chart_df = df.head(10).copy()
                                if not chart_df.empty:
                                    chart_df = chart_df.sort_values('2025排名')
                                    st.bar_chart(chart_df.set_index('学校名称')['2025分数'])
                        else:
                            st.warning("未找到相关排名数据")

                except pymysql.Error as e:
                    st.error(f"查询失败: {e}")
                finally:
                    connection.close()


def interactive_crawler_ui():
    """交互式爬虫界面"""
    print("=" * 60)
    print("欢迎使用考研数据爬虫系统")
    print("=" * 60)

    while True:
        print("\n请选择操作：")
        print("1. 按地区搜索爬取考研专业信息")
        print("2. 按学校搜索爬取考研专业信息")
        print("3. 运行软科排名爬虫")
        print("4. 删除数据")
        print("5. 退出")

        choice = input("请输入选项 (1-5): ").strip()

        if choice == "1":
            crawl_by_region()
        elif choice == "2":
            crawl_by_school()
        elif choice == "3":
            crawl_shanghai_ranking()
        elif choice == "4":
            delete_data()
        elif choice == "5":
            print("感谢使用，再见！")
            break
        else:
            print("无效选项，请重新输入")


def crawl_by_region():
    """按地区爬取"""
    print("\n=== 按地区爬取考研专业信息 ===")
    spider = CompleteInfoSpider()

    regions, features = spider.select_region_and_features()

    if not regions:
        print("未选择任何地区，返回主菜单")
        return

    print(f"\n已选择地区: {regions}")
    print(f"已选择院校特性: {features}")

    confirm = input("确认开始爬取吗？(y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消爬取")
        return

    print("\n开始爬取...")
    spider.crawl_by_regions_and_features(regions, features)
    print(f"\n爬取完成！数据已保存到数据库和Excel文件: {spider.excel_filename}")


def crawl_by_school():
    """按学校爬取"""
    print("\n=== 按学校爬取考研专业信息 ===")
    spider = CompleteInfoSpider()

    school_names = spider.select_schools_by_name()

    if not school_names:
        print("未输入任何学校名称，返回主菜单")
        return

    print(f"\n已选择学校: {school_names}")

    confirm = input("确认开始爬取吗？(y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消爬取")
        return

    print("\n开始爬取...")
    spider.crawl_by_school_names(school_names)
    print(f"\n爬取完成！数据已保存到数据库和Excel文件: {spider.excel_filename}")


def crawl_shanghai_ranking():
    """爬取软科排名"""
    print("\n=== 爬取软科排名 ===")

    spider = ShanghaiRankingSpider(headless=True)

    try:
        print("\n正在从软科官网获取学科列表...")
        subjects_data = spider.fetch_all_subjects_from_web()

        if not subjects_data:
            print("获取学科列表失败")
            return

        subject_mapping = spider.display_all_subjects()

        if not subject_mapping:
            print("未找到可用学科")
            return

        # 显示学科列表给用户
        print("\n可用的学科列表：")
        print("-" * 60)

        sorted_categories = {}
        for idx in subject_mapping:
            subject_code, subject_name, category_code, category_name = subject_mapping[idx]
            if category_name not in sorted_categories:
                sorted_categories[category_name] = []
            sorted_categories[category_name].append((idx, subject_code, subject_name))

        # 按类别显示学科
        for category_name in sorted(sorted_categories.keys()):
            print(f"\n{category_name}:")
            for idx, subject_code, subject_name in sorted_categories[category_name]:
                print(f"  {idx:3d}. {subject_code} {subject_name}")

        print("-" * 60)

        print("\n请选择爬取模式：")
        print("1. 选择特定学科爬取")
        print("2. 爬取所有学科（耗时较长）")
        print("3. 返回主菜单")

        mode = input("\n请输入选项 (1-3): ").strip()

        if mode == "1":
            while True:
                selection = input("\n请输入要爬取的学科编号（多个用逗号分隔）: ").strip()

                if not selection:
                    print("输入为空，请重新输入")
                    continue

                try:
                    selected_indices = [int(idx.strip()) for idx in selection.split(',') if idx.strip().isdigit()]

                    if not selected_indices:
                        print("未输入有效编号，请重新输入")
                        continue

                    valid_indices = [idx for idx in selected_indices if idx in subject_mapping]

                    if not valid_indices:
                        print("无效的编号，请重新输入")
                        continue

                    selected_subjects = []
                    for idx in valid_indices:
                        subject_code, subject_name, _, _ = subject_mapping[idx]
                        selected_subjects.append((subject_code, subject_name))
                        print(f"  - {subject_code} {subject_name}")

                    confirm = input(f"\n确认爬取以上 {len(selected_subjects)} 个学科吗？(y/n): ").strip().lower()
                    if confirm != 'y':
                        print("已取消爬取")
                        continue

                    print("\n开始爬取...")
                    all_data = []

                    for i, (subject_code, subject_name) in enumerate(selected_subjects):
                        print(f"\n[{i + 1}/{len(selected_subjects)}] 爬取学科: {subject_name} ({subject_code})")
                        data = spider.fetch_subject_data(subject_code, subject_name, max_pages=3)
                        if data:
                            spider.save_subject_rankings_to_db(data)
                            all_data.extend(data)
                            print(f"  已爬取 {len(data)} 条数据")
                        else:
                            print(f"  未获取到数据")

                        if i < len(selected_subjects) - 1:
                            delay = random.uniform(3, 8)
                            print(f"  等待 {delay:.1f} 秒后继续...")
                            time.sleep(delay)

                    print(f"\n爬取完成，共获取 {len(all_data)} 条数据")
                    break

                except ValueError:
                    print("输入格式错误，请重新输入")

        elif mode == "2":
            total_subjects = len(subject_mapping)
            print(f"\n警告：将爬取全部 {total_subjects} 个学科，这可能需要很长时间！")

            confirm = input("确认爬取所有学科吗？(y/n): ").strip().lower()
            if confirm != 'y':
                print("已取消爬取")
                return

            print("\n开始爬取所有学科...")
            all_data = []
            current = 1

            for idx in range(1, total_subjects + 1):
                subject_code, subject_name, _, _ = subject_mapping[idx]
                print(f"\n[{current}/{total_subjects}] 爬取学科: {subject_name} ({subject_code})")

                data = spider.fetch_subject_data(subject_code, subject_name, max_pages=2)
                if data:
                    spider.save_subject_rankings_to_db(data)
                    all_data.extend(data)
                    print(f"  已爬取 {len(data)} 条数据")
                else:
                    print(f"  未获取到数据")

                current += 1

                if current <= total_subjects:
                    delay = random.uniform(5, 10)
                    print(f"  等待 {delay:.1f} 秒后继续...")
                    time.sleep(delay)

            print(f"\n所有学科爬取完成，共获取 {len(all_data)} 条数据")

        elif mode == "3":
            print("返回主菜单")

        else:
            print("无效选项，返回主菜单")

    except Exception as e:
        print(f"爬取过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        spider.close_driver()


def delete_data():
    """删除数据"""
    print("\n=== 删除数据 ===")

    print("\n请选择删除类型：")
    print("1. 按地区删除考研专业信息")
    print("2. 按学校删除考研专业信息")
    print("3. 按学科删除软科排名")
    print("4. 清空所有软科排名数据")
    print("5. 返回主菜单")

    choice = input("请输入选项 (1-5): ").strip()

    if choice == "1":
        region = input("请输入要删除的地区名称: ").strip()
        if region:
            spider = CompleteInfoSpider()
            if spider.delete_region_data(region):
                print(f"成功删除地区 '{region}' 的所有数据")
            else:
                print(f"删除地区 '{region}' 数据失败")

    elif choice == "2":
        school_name = input("请输入要删除的学校名称: ").strip()
        if school_name:
            spider = CompleteInfoSpider()
            if spider.delete_school_data(school_name, 'school'):
                print(f"成功删除学校 '{school_name}' 的所有数据")
            else:
                print(f"删除学校 '{school_name}' 数据失败")

    elif choice == "3":
        subject_name = input("请输入要删除的学科名称: ").strip()
        if subject_name:
            spider = ShanghaiRankingSpider()
            print(f"删除学科 '{subject_name}' 数据功能需在代码中实现")

    elif choice == "4":
        spider = ShanghaiRankingSpider()
        print("清空所有软科排名数据功能需在代码中实现")

    elif choice == "5":
        print("返回主菜单")

    else:
        print("无效选项，返回主菜单")


def is_running_in_streamlit():
    """检查是否在Streamlit环境中运行"""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except:
        return False


def main():
    """主函数"""
    # 初始化数据库
    if 'db_initialized' not in st.session_state:
        if init_database():
            st.session_state.db_initialized = True
        else:
            st.error("数据库初始化失败，请检查数据库连接")
            return

    # 页面路由
    if 'page' not in st.session_state:
        st.session_state.page = "login"

    # 根据当前页面显示相应内容
    if st.session_state.page == "login":
        login_page()
    elif st.session_state.page == "register":
        register_page()
    elif st.session_state.page == "main":
        if 'user' in st.session_state:
            main_page()
        else:
            st.session_state.page = "login"
            st.rerun()
    elif st.session_state.page == "data_query":
        if 'user' in st.session_state:
            data_query_page()
        else:
            st.session_state.page = "login"
            st.rerun()


if __name__ == "__main__":
    # 自动检测运行环境
    if is_running_in_streamlit():
        main()
    else:
        interactive_crawler_ui()
