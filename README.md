# 🎓 考研AI问答与数据分析系统

> 一个集数据采集、智能问答、数据可视化于一体的端到端考研信息系统

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-orange.svg)](https://www.mysql.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 📖 目录
- [项目简介](#项目简介)
- [✨ 功能特性](#-功能特性)
- [🏗️ 系统架构](#️-系统架构)
- [🚀 快速开始](#-快速开始)
  - [环境要求](#环境要求)
  - [安装步骤](#安装步骤)
  - [配置说明](#配置说明)
- [📊 数据库设计](#-数据库设计)
- [🖥️ 使用说明](#️-使用说明)
  - [数据采集](#数据采集)
  - [Web应用](#web应用)
- [🔧 项目结构](#-项目结构)
- [🤖 AI使用说明](#-ai使用说明)
- [📈 数据统计](#-数据统计)
- [🎯 核心查询示例](#-核心查询示例)
- [⚠️ 注意事项](#️-注意事项)
- [📄 许可证](#-许可证)

## 项目简介

随着考研竞争日益激烈，考生对院校专业信息的准确性和全面性需求不断增加。本项目旨在构建一个**集数据采集、智能问答、数据可视化于一体的端到端考研信息系统**，帮助考生快速获取准确的考研信息。

系统整合了中国研究生招生信息网的官方招生数据和软科排名网站的学科评估数据，通过大语言模型提供智能问答服务，为考研学子提供一站式信息查询平台。

## ✨ 功能特性

### 📥 数据采集
- **多线程爬虫**：支持并发爬取，提高数据采集效率
- **智能容错**：自动重试、浏览器重启、异常处理机制
- **数据去重**：基于唯一键自动去重，保证数据质量
- **断点续传**：记录爬取进度，支持中断后继续爬取

### 🗄️ 数据存储
- **结构化存储**：MySQL关系型数据库，支持复杂查询
- **数据关联**：考研信息与学科排名数据关联查询
- **用户数据**：完整的用户系统和聊天历史记录

### 🤖 智能问答
- **AI驱动**：基于DeepSeek大语言模型的智能问答
- **数据准确**：所有回答均基于数据库真实数据
- **智能解析**：自动识别问题中的学校、专业关键词

### 📊 数据可视化
- **条件查询**：多字段组合查询，支持模糊匹配
- **统计分析**：专业热度、地区分布等数据统计
- **排名查询**：软科学科排名查询与可视化展示

### 👤 用户系统
- **安全认证**：用户注册、登录、密码哈希存储
- **历史记录**：保存用户问答历史，支持查看和清空
- **个性化**：基于用户历史的个性化查询

## 🏗️ 系统架构

```
考研AI问答系统
├── 数据采集层
│   ├── 研招网爬虫 (ThreadSafeSpider)
│   ├── 软科排名爬虫 (ShanghaiRankingSpider)
│   └── 数据清洗与验证
├── 数据存储层
│   ├── MySQL数据库
│   ├── 数据持久化
│   └── 数据备份
├── 业务逻辑层
│   ├── 用户认证
│   ├── 数据查询
│   ├── AI问答引擎
│   └── 数据可视化
└── 表现层
    ├── Streamlit Web界面
    ├── 用户交互
    └── 结果展示
```

## 🚀 快速开始

### 环境要求

- **Python**: 3.8 或更高版本
- **MySQL**: 8.0 或更高版本
- **Edge浏览器**: 最新版本（用于Selenium爬虫）
- **操作系统**: Windows 10/11 或 Linux/macOS

### 安装步骤

1. **克隆项目**
   ```bash
   git clone https://github.com/[你的用户名]/kaoyan-ai-assistant.git
   cd kaoyan-ai-assistant
   ```

2. **安装Python依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置MySQL数据库**
   ```sql
   -- 创建数据库
   CREATE DATABASE kaoyan_data CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   
   -- 创建用户并授权
   CREATE USER 'kaoyan_user'@'localhost' IDENTIFIED BY 'your_password';
   GRANT ALL PRIVILEGES ON kaoyan_data.* TO 'kaoyan_user'@'localhost';
   FLUSH PRIVILEGES;
   ```

4. **下载Edge浏览器驱动**
   - 访问 https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/
   - 下载与你的Edge浏览器版本匹配的驱动
   - 将`msedgedriver.exe`放置在项目根目录

### 配置说明

1. **数据库配置**
   在代码中修改以下配置（位于`main.py`的`CompleteInfoSpider`和`ShanghaiRankingSpider`类中）：
   ```python
   self.db_config = {
       'host': 'localhost',
       'user': 'root',           # 改为你的MySQL用户名
       'password': 'your_password', # 改为你的MySQL密码
       'database': 'kaoyan_data'
   }
   ```

2. **API密钥配置**
   在`.streamlit/secrets.toml`文件中配置DeepSeek API密钥：
   ```toml
   DEEPSEEK_API_KEY = "your_deepseek_api_key_here"
   ```

## 📊 数据库设计

系统包含5个核心数据表：

### 1. **users** - 用户表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 用户ID，主键 |
| username | VARCHAR(50) | 用户名，唯一 |
| email | VARCHAR(100) | 邮箱，唯一 |
| password_hash | VARCHAR(255) | 密码哈希值 |
| created_at | TIMESTAMP | 创建时间 |
| last_login | TIMESTAMP | 最后登录时间 |
| is_active | BOOLEAN | 是否激活 |

### 2. **exam_subjects** - 考研专业信息表
存储从研招网爬取的招生专业信息，包含学校、专业、研究方向、考试科目等详细信息。

### 3. **shanghai_subject_rankings** - 软科排名表
存储软科2024-2025年学科排名数据，包含学科代码、学校名称、排名位置、分数等。

### 4. **chat_history** - 聊天历史表
记录用户与AI的问答历史，支持历史记录查询。

### 5. **crawl_progress** - 爬虫进度表
记录爬虫执行状态，支持断点续爬。

## 🖥️ 使用说明

### 数据采集

#### 运行研招网爬虫
```bash
# 直接运行main.py中的爬虫部分
python main.py
```
程序将启动交互式爬虫界面，您可以选择：
1. **按地区搜索**：选择地区和院校特性，批量爬取学校专业信息
2. **按学校搜索**：输入具体学校名称，爬取指定学校信息

#### 运行软科排名爬虫
```python
# 在Python交互环境中运行
from main import ShanghaiRankingSpider

spider = ShanghaiRankingSpider(headless=False)
# 爬取单个学科测试
spider.test_single_subject(subject_code='0701', subject_name='数学', max_pages=3)
# 导出数据到Excel
spider.export_to_excel()
spider.close_driver()
```

### Web应用

#### 启动Web服务
```bash
streamlit run main.py
```

#### 主要功能界面

1. **登录/注册页面**
   - 新用户注册，需要验证邮箱格式
   - 已注册用户登录

2. **AI问答主界面**
   - **智能问答**：输入自然语言问题，获取基于数据库的准确回答
   - **示例问题**：提供常见问题示例，一键提问
   - **历史记录**：查看和清空聊天历史
   - **数据库预览**：展开查看AI回答背后的原始数据

3. **数据查询页面**
   - **条件查询**：按学校、专业等条件筛选数据
   - **学校浏览**：按学校查看所有专业信息
   - **数据统计**：查看专业热度、地区分布等统计信息
   - **软科排名**：查询学科排名，支持前N名筛选

## 🔧 项目结构

```
kaoyan_assistant/
├── README.md                   # 项目说明文档
├── requirements.txt            # Python依赖包
├── main.py                     # 主程序文件（包含所有功能）
├── .streamlit/                 # Streamlit配置文件
│   └── secrets.toml           # API密钥配置文件
├── msedgedriver.exe           # Edge浏览器驱动
└── screenshots/               # 系统截图
```

## 🤖 AI使用说明

本系统使用了DeepSeek大语言模型API来生成智能回答：

### AI使用原则
1. **数据驱动**：所有回答均基于数据库真实信息
2. **准确优先**：优先保证信息的准确性
3. **结构清晰**：按学校、专业、研究方向组织回答
4. **完整呈现**：列出数据库中所有相关信息

### 提示词设计
系统使用精心设计的提示词来约束AI行为，确保回答的准确性和可靠性。

## 📈 数据统计

系统内置数据统计功能，可以实时查看：
- **总记录数**：数据库中的专业信息总数
- **覆盖高校数**：数据涵盖的学校数量
- **专业数量**：不同的专业种类数
- **热门专业TOP 10**：最常出现的专业排名
- **地区分布**：各地区的专业分布情况

## 🎯 核心查询示例

系统支持多种复杂查询，例如：

### 多表联接查询
```sql
-- 查询学校专业的详细信息及软科排名
SELECT es.school_name, es.major_name, es.research_direction,
       sr.ranking_position_2025, sr.ranking_position_2024
FROM exam_subjects es
LEFT JOIN shanghai_subject_rankings sr
ON es.school_name = sr.school_name
WHERE es.school_name = '北京大学'
AND es.major_name LIKE '%计算机%'
```

### 聚合统计查询
```sql
-- 统计各地区计算机相关专业数量
SELECT region, COUNT(*) as major_count,
       COUNT(DISTINCT school_name) as school_count
FROM exam_subjects
WHERE major_name LIKE '%计算机%'
GROUP BY region
ORDER BY major_count DESC;
```

## ⚠️ 注意事项

1. **数据时效性**：爬虫数据基于当时网站状态，招生信息以官方最新发布为准
2. **API限制**：DeepSeek API有调用频率限制，请合理使用
3. **爬虫礼仪**：设置合理的请求间隔，避免对目标网站造成压力
4. **数据备份**：定期备份数据库，防止数据丢失
5. **隐私保护**：妥善保管API密钥和数据库密码

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。