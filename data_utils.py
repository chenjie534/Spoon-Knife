# data_utils.py
from sqlalchemy import  func, Float
from datetime import datetime, timedelta
from database import Session, LMAPrediction, MagneticData, PictureDefect,Event5, RopeDetails
from datetime import date

# 给home传需要的数据
def get_home_data(query_date):
    # 获取预测数据
    session=Session()
    results = session.query(LMAPrediction).filter(LMAPrediction.date == query_date).all()
    health_scores = [{'meter': r.position, 'Probability': r.LMA_day_1} for r in results] if results else []

    # 今日数据查询逻辑
    # 查询 event_5 表中的 position 和 LMA_value
    event5_query = session.query(
        Event5.position.label("position"),
        Event5.LMA_value.label("LMA_value")
    ).filter(Event5.date == query_date)

    # 查询 MagneticData 表中的 position，排除那些已经在 event_5 表中的 position
    magnetic_query = session.query(
        MagneticData.position.label("position"),
        func.cast(0, Float).label("LMA_value")
    ).filter(
        MagneticData.date == query_date,
        ~MagneticData.position.in_(
            session.query(Event5.position).filter(Event5.date == query_date)
        )
    )

    # 使用 UNION 合并两个查询，得到最终结果
    final_query = event5_query.union(magnetic_query)
    today_results = final_query.all()

    # 将查询结果转换为 {'meter':, 'Probability': } 格式
    today_data = [{'meter': r.position, 'Probability': r.LMA_value} for r in today_results] if today_results else []

    # 获取磁场数据
    magnetic_results = session.query(MagneticData).filter(MagneticData.date == query_date).all()
    magnetic_value = [
        {
            'meter': record.position,
            'Sensor_1': record.sensor1,
            'Sensor_2': record.sensor2,
            'Sensor_3': record.sensor3,
            'Sensor_4': record.sensor4,
            'Sensor_5': record.sensor5,
            'Sensor_6': record.sensor6
        } for record in magnetic_results
    ] if magnetic_results else []

    return {
        "health_scores": health_scores,
        "today_data": today_data,
        "magnetic_value": magnetic_value
    }


# 给problem页面传入没有完全过滤的值
def get_problems_data_internal():
    # 获取指定日期的所有数据
    session = Session()
    base_date = datetime.now().date()
    start_date = base_date - timedelta(days=7)
    end_date = base_date

    # 创建一个完整的日期列表
    #date_list = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]

    # 获取磁性数据
    magnetic_value = session.query(MagneticData).filter(MagneticData.date == base_date).all()
    # 获取缺陷数据
    defects = session.query(PictureDefect).filter(PictureDefect.date == base_date).all()

    # 获取当天健康得分数据,获取历史健康得分数据
    #historical_results = session.query(HealthScore).filter(HealthScore.date.between(start_date, end_date)).all()
    today_data,historical_results=get_historical_and_today_data(start_date,end_date)

    # 格式化返回数据
    response_data = {
        "magnetic_value": [
            {
                'date': record.date.strftime('%Y-%m-%d'),
                'meter': record.position,
                'Sensor_1': record.sensor1,
                'Sensor_2': record.sensor2,
                'Sensor_3': record.sensor3,
                'Sensor_4': record.sensor4,
                'Sensor_5': record.sensor5,
                'Sensor_6': record.sensor6
            } for record in magnetic_value
        ],
        "defects": [
            {
                'meter': defect.position,
                'possible defect': defect.issue  # 不包含图片数据
            } for defect in defects
        ],
        "today_data": today_data
        ,
        "historical_data": historical_results

    }
    return response_data

# 给healthiness_prediction页面传入没有完全过滤的值
def get_history_data_internal():
    session = Session()
    # 获取指定日期的所有数据
    base_date = datetime.now().date()
    start_date = base_date - timedelta(days=7)
    end_date = base_date + timedelta(days=1)

    # 创建一个完整的日期列表
    #date_list = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]

    # 获取磁性数据
    magnetic_value = session.query(MagneticData).filter(MagneticData.date == base_date).all()
    # 获取缺陷数据
    defects = session.query(PictureDefect).filter(PictureDefect.date == base_date).all()
    # 获取LMA_tomorrow数据
    future_data_results = session.query(LMAPrediction).filter(LMAPrediction.date == base_date).all()
    future_data = [
        {
            'date': data.date.strftime('%Y-%m-%d'),
            'meter': data.position,
            'Probability': data.LMA_day_1
        } for data in future_data_results
    ] if future_data_results else []
    # 获取当天健康得分数据,获取历史健康得分数据
    # historical_results = session.query(HealthScore).filter(HealthScore.date.between(start_date, end_date)).all()
    today_data, historical_results = get_historical_and_today_data(start_date, end_date)

    # 合并 future_data 和 historical_results
    combined_historical_data = historical_results + future_data


    # 格式化返回数据
    response_data = {
        "magnetic_value": [
            {
                'date': record.date.strftime('%Y-%m-%d'),
                'meter': record.position,
                'Sensor_1': record.sensor1,
                'Sensor_2': record.sensor2,
                'Sensor_3': record.sensor3,
                'Sensor_4': record.sensor4,
                'Sensor_5': record.sensor5,
                'Sensor_6': record.sensor6
            } for record in magnetic_value
        ],
        "defects": [
            {
                'meter': defect.position,
                'possible defect': defect.issue  # 不包含图片数据
            } for defect in defects
        ],
        "today_data": today_data,
        "historical_data": combined_historical_data
    }
    return response_data


# 过滤器
def filter_historical_data(historical_data, meter):
    # 获取从 start_date 到 base_date 的所有日期
    base_date = datetime.now().date()
    start_date = base_date - timedelta(days=7)
    date_list = [start_date + timedelta(days=x) for x in range(8)]  # 8 天

    # 创建一个字典，初始化每个日期为缺失的空数据
    historical_data_dict = {date: {'date': date.strftime('%d/%m/%Y'), 'meter': float(meter), 'Probability': None} for date in date_list}

    # 筛选历史数据并填充字典
    for record in historical_data:
        if record['meter'] == float(meter):
            record_date = datetime.strptime(record['date'], '%Y-%m-%d').date()
            historical_data_dict[record_date] = {
                'date': record_date.strftime('%d/%m/%Y'),
                'meter': record['meter'],
                'Probability': record['Probability']
            }

    # 获取排序后的历史数据，按日期升序排列
    sorted_data = sorted(historical_data_dict.values(), key=lambda x: x['date'])

    return sorted_data




def filter_problems_data(historical_data, meter):
    # 获取从 start_date 到 base_date 的所有日期
    # 获取从 start_date 到 base_date 的所有日期
    base_date = datetime.now().date()
    start_date = base_date - timedelta(days=7)
    date_list = [start_date + timedelta(days=x) for x in range(9)]  # 9 天

    # 创建一个字典，初始化每个日期为缺失的空数据
    historical_data_dict = {date: {'date': date.strftime('%d/%m/%Y'), 'meter': float(meter), 'Probability': None} for date in date_list}

    # 筛选历史数据并填充字典
    for record in historical_data:
        if record['meter'] == float(meter):
            record_date = datetime.strptime(record['date'], '%Y-%m-%d').date()
            # 仅在日期范围内更新数据
            if record_date in historical_data_dict:
                historical_data_dict[record_date] = {
                    'date': record_date.strftime('%d/%m/%Y'),
                    'meter': record['meter'],
                    'Probability': record['Probability']
                }

    # 获取排序后的历史数据，按日期升序排列
    sorted_data = sorted(historical_data_dict.values(), key=lambda x: datetime.strptime(x['date'], '%d/%m/%Y'))

    return sorted_data



# 封装函数，用于获取 event_5 和 MagneticData 的区间历史数据
def get_historical_and_today_data(start_date, end_date):
    session = Session()
    # 查询 event_5 表中的 position 和 LMA_value，日期在 start_date 和 end_date 之间
    event5_query = session.query(
        Event5.date.label("date"),
        Event5.position.label("position"),
        Event5.LMA_value.label("LMA_value")
    ).filter(Event5.date.between(start_date, end_date))

    # 查询 MagneticData 表中的 position，排除那些已经在 event_5 表中的 position，日期在 start_date 和 end_date 之间
    magnetic_query = session.query(
        MagneticData.date.label("date"),
        MagneticData.position.label("position"),
        func.cast(0, Float).label("LMA_value")
    ).filter(
        MagneticData.date.between(start_date, end_date),
        ~MagneticData.position.in_(
            session.query(Event5.position).filter(Event5.date.between(start_date, end_date))
        )
    )

    # 使用 UNION 合并两个查询，得到最终结果
    final_query = event5_query.union(magnetic_query)
    results = final_query.all()

    # 将查询结果格式化为指定格式
    historical_data = [
        {
            'date': result.date.strftime('%Y-%m-%d'),
            'meter': result.position,
            'Probability': result.LMA_value
        } for result in results
    ]

    # 分离今日数据
    today_data = [record for record in historical_data if record['date'] == end_date.strftime('%Y-%m-%d')]

    return today_data, historical_data





def get_combined_data(day, meter):
    session = Session()
    today_date = date.today()

    # 获取前七天的日期
    seven_days_ago = today_date - timedelta(days=7)

    # 先获取历史数据（前七天到今天）
    historical_data = []
    try:
        # 查询 Event5 表中的 position 和 LMA_value，日期在前七天到今天之间，且 position 为传入的 meter
        event5_query = session.query(
            Event5.date.label("date"),
            Event5.position.label("position"),
            Event5.LMA_value.label("LMA_value")
        ).filter(
            Event5.position == meter,
            Event5.date.between(seven_days_ago, today_date)
        )

        results = event5_query.all()

        # 将查询结果格式化为指定格式
        historical_data = [
            {
                'date': result.date.strftime('%d/%m/%Y'),  # 使用 '%d/%m/%Y' 格式
                'meter': result.position,
                'Probability': result.LMA_value
            } for result in results
        ]

        # 确保前七天到今天每一天的数据都有，如果某一天缺失数据，则手动填充
        all_dates = [seven_days_ago + timedelta(days=i) for i in range(8)]  # 从前七天到今天，共8天
        all_dates_str = [date_.strftime('%d/%m/%Y') for date_ in all_dates]  # 转换为字符串格式 '%d/%m/%Y'

        # 遍历所有日期，补充缺失的日期数据
        for date_str in all_dates_str:
            if not any(record['date'] == date_str for record in historical_data):
                historical_data.append({
                    'date': date_str,
                    'meter': meter,
                    'Probability': 0  # 如果数据缺失，设为 0
                })

        # 获取当天数据以及后 day 天的数据
        prediction_data = []
        result = session.query(LMAPrediction).filter_by(position=meter).filter(LMAPrediction.date == today_date).first()

        if result:  # 如果今天有预测数据
            for i in range(1, day + 1):
                LMA_value = getattr(result, f'LMA_day_{i}', None)  # 动态获取 LMA_day_i

                # 即使 LMA_value 为 None，也需要把这一天的数据加上
                prediction_data.append({
                    'date': (today_date + timedelta(days=i)).strftime('%d/%m/%Y'),  # 使用 '%d/%m/%Y' 格式
                    'meter': result.position,
                    'Probability': LMA_value  # 如果 LMA_value 为 None，直接返回 None
                })

        # 合并历史数据和预测数据
        combined_data = historical_data + prediction_data

        # 按日期升序排列
        combined_data_sorted = sorted(combined_data, key=lambda x: datetime.strptime(x['date'], '%d/%m/%Y'))

        return combined_data_sorted

    finally:
        session.close()


def get_today_event1_data():
    session = Session()
    today = date.today()

    # 查询今天的 rope_details 数据
    rope_data = session.query(RopeDetails).filter(RopeDetails.time == today).first()

    if rope_data:
        data = {
            'ropeLen': str(rope_data.ropeLen),
            'ropeCnt': str(rope_data.ropeCnt),
            'ropeManuf': rope_data.ropeManuf,
            'ropeSpecific': rope_data.ropeSpecific,
            'ropeDm': str(rope_data.ropeDm),
            'ropeThigh': str(rope_data.ropeThigh),
            'ropeSilk': str(rope_data.ropeSilk),
            'ropeMaterial': rope_data.ropeMaterial,
            'ropeCore': rope_data.ropeCore,
            'ropeSurface': rope_data.ropeSurface,
            'ropeTwist': rope_data.ropeTwist,
            'ropeFknMin': str(rope_data.ropeFknMin),
            'ropeFknFact': str(rope_data.ropeFknFact),
            'ropeStructure': rope_data.ropeStructure,
            'ropeUsedate': str(rope_data.ropeUsedate)
        }
        return data
    else:
        return None  # 如果没有找到今天的数据，返回 None


def report_pdf_Rope_Issue(report_type,date_str):
    #将数据库中数据放至word中对应位置
    #将word转为pdf

    #返回文件保存路径
    pdf_file_path="..\FlaskCode\报告模板.docx"
    return pdf_file_path


def report_pdf_Trend_Analysis(report_type,date_str):

    # 返回文件保存路径
    pdf_file_path = "..\FlaskCode\报告模板.docx"
    return pdf_file_path
