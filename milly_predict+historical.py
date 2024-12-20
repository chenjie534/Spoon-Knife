from flask import Flask, render_template, request, redirect, url_for, make_response, session, jsonify, Response, flash, session as flask_session,send_file
# import pandas as pd
from flask_socketio import SocketIO
import cv2
import time
from datetime import datetime, timedelta
import requests

import subprocess
import threading
import queue
import atexit
from database import PictureData, Defect, Event5, MagneticData, \
    PictureDefect,User, Session,Event0, LMAPrediction
from data_utils import get_home_data, get_problems_data_internal, filter_problems_data,filter_historical_data, get_history_data_internal, report_pdf_Trend_Analysis, get_today_event1_data, get_combined_data
#from pdf_utils import report_pdf_Rope_Issue
from ultralytics import YOLO
import os
import numpy as np
from collections import deque
app = Flask(__name__)
socketio = SocketIO(app)
app.secret_key = 'your_secret_key'  # 替换为任何随机字符串


lock = threading.Lock()
global_email = None



# 加载 YOLO 模型
relative_path_trained_model = "best3.pt"
model = YOLO(os.path.abspath(relative_path_trained_model))

# 默认的 RTSP URL（可以根据需要修改）
DEFAULT_RTSP_URL = "rtsp://127.0.0.1/live/vi1"
rtsp_url = DEFAULT_RTSP_URL  # 默认 RTSP URL
cap = None
ffmpeg_process = None  # 用于保存 FFmpeg 进程对象
is_connected = False  # 标志，指示是否已经连接 RTSP 流
change = False  # 标志，指示是否需要切换流

# 最大重试次数和重试间隔
MAX_RETRIES = 5
RETRY_INTERVAL = 5  # seconds

# 创建一个长度为10的双端队列
speed_queue = deque(maxlen=10)
# 创建一个锁以确保线程安全
queue_lock = threading.Lock()


@app.teardown_appcontext
def remove_session(exception=None):
    Session.remove()

@app.route('/', methods=['GET', 'POST'])

def login():
    if request.method == 'POST':
        username = request.form.get('username-or-email')
        password = request.form.get('password')
        remember_me = request.form.get('remember_me') == 'on'  # 复选框选中时值为 'on'
        # response = requests.get('http://localhost:5000/login', params={'username': username, 'password': password, 'remember_me': remember_me})
        # user_authenticated = (response.status_code == 200)
        user = Session.query(User).filter_by(username=username).first()
        if user and user.check_password(password):
            flask_session['user_id'] = user.id
            flash('登录成功！', 'success')
            return redirect(url_for('home'))

        else:
            flash('用户名或密码错误！')
            return render_template('login.html')
    return render_template('login.html')


@app.route('/forgotpass', methods=['GET', 'POST'])
def forgotpass():
    if request.method == 'POST':
        email = request.form.get('email')
        global global_email
        global_email = email
        return redirect(url_for('resetpass'))
    return render_template('forgotpass.html')

@app.route('/resetpass', methods=['GET', 'POST'])
def resetpass():
    if request.method == 'POST':
        password = request.form.get('password')
        response = requests.get('http://localhost:5000/resetpass', params={'email': global_email, 'password': password})
        if response.status_code:
            return render_template('resetpass_successful.html')
    return render_template('resetpass.html')

@app.route('/resetpass_successful')
def resetpass_successful():
    return render_template('resetpass_successful.html')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        #email = request.form.get('email')
        password = request.form.get('password')

        # 检查用户名是否已存在
        existing_user = Session.query(User).filter_by(username=username).first()
        if existing_user:
            flash('用户名已存在，请使用其他用户名。', 'warning')
            return render_template('signup.html')

        # 创建新用户
        new_user = User(username=username)
        new_user.set_password(password)  # 设置加密密码
        Session.add(new_user)
        Session.commit()

        flash('注册成功！现在可以登录了。', 'success')
        return redirect(url_for('login'))



    return render_template('signup.html')

@app.route('/signup_successful')
def signup_successful():
    return render_template('signup_successful.html')

@app.route('/signup_failed')
def signup_failed():
    return render_template('signup_failed.html')

meter_historical = -1  # 初始化meter_historical为 -1
@app.route('/home', methods=['GET', 'POST'])
def home():
    # 直接调用合并后的函数获取所有数据
    query_date = datetime.today().date()

    home_data = get_home_data(query_date)

    data = home_data.get("health_scores")
    today_data = home_data.get("today_data")
    magnetic_value = home_data.get("magnetic_value")
    query_date_str = datetime.today().date().strftime('%Y-%m-%d')

    if request.method == 'POST':
        # Get the meter number from the form
        meter = request.form.get('meter')
        global meter_historical
        if meter != "-1":
            meter_historical = meter
            return redirect(url_for('healthiness_prediction', meter=meter_historical))
        else:
            if meter_historical != -1:
                return redirect(url_for('healthiness_prediction', meter=meter_historical))
            else:
                return redirect(url_for('healthiness_prediction', meter=1))

    # Render the template with the data
    return render_template('home.html', data=data,  today_data=today_data, magnetic_value=magnetic_value,
                           date=query_date_str)

@app.route('/generate_report', methods=['POST'])
def generate_report():
    report_type = request.form.get('reportType')
    date_str = request.form.get('date')  # 获取表单中的日期字符串
    # 设置默认日期
    if not date_str:
        if report_type == 'Rope Issue':
            date_str = datetime.now().strftime('%Y-%m-%d')  # 默认为今天
        elif report_type == 'Trend Analysis':
            date_str = 'One Day Trend'  # 默认为一天趋势
    if report_type == 'Rope Issue':
        # 调用 report_pdf_Day 函数
        pdf_path = report_pdf_Rope_Issue(report_type,date_str)
        return send_file(pdf_path, as_attachment=True)
    elif report_type == 'Trend Analysis':
        # 调用 report_pdf_Week 函数
        pdf_path = report_pdf_Trend_Analysis(report_type,date_str)
        return send_file(pdf_path, as_attachment=True)
    else:
        return 'Invalid report type', 400


@app.route('/rope_details')
def rope_details():
    data = get_today_event1_data()

    return render_template('rope_details.html', data=data)

@app.route('/account_setting')
def account_setting():
    # 账户名 权限等级 更新日期 操作人员 操作（密码 编辑 删除）
    data = [
        {
            "account_name": "EYO",
            "permission_level": "OND",
        },
        {
            "account_name": "EYO1",
            "permission_level": "OND1",
        },
    ]
    return  render_template('account_setting.html', data=data)

@app.route('/account_add_account', methods=['POST'])
def account_add_account():
    new_account_data = request.get_json()  # 获取前端传来的JSON格式数据
    username = new_account_data.get('username')
    permission_level = new_account_data.get('permission_level')
    # 检查账户名是否已存在
    # if existing_account:
    #     return {'success': False, 'message': 'Account name already exists'}, 400
    # 创建新账户对象并插入数据库，该账户的用户名为username、权限等级为permission_level、密码为123456

    return {'success': True, 'message': 'Account added successfully'}, 200

@app.route('/account_reset_password', methods=['POST'])
def account_reset_password():
    account_data = request.get_json()
    username = account_data.get('username')
    # 这里添加具体的密码重置逻辑，可以将该账户的密码统一重置为123456

    # return {'success': False, 'message': 'Account not found'}, 404
    return {'success': True,'message': 'Password reset successfully'}, 200

@app.route('/account_update_name', methods=['POST'])
def account_update_name():
    update_data = request.get_json()
    old_username = update_data.get('old_username')
    new_username = update_data.get('new_username')
    # 这里添加具体的更新用户名逻辑

    # return {'success': False, 'message': 'Account not found'}, 404
    return {'success': True, 'message': 'Account name updated successfully'}, 200

@app.route('/account_delete', methods=['POST'])
def account_delete():
    account_data = request.get_json()
    username = account_data.get('username')
    #这里添加具体的删除账户名为username的用户的逻辑

    # return {'success': False,'message': 'Account not found'}, 404
    return {'success': True, 'message': 'Account deleted successfully'}, 200

@app.route('/healthiness_prediction/<path:meter>', methods=['GET', 'POST'])
def healthiness_prediction(meter):
    # Use the internal function to get all data
    data = get_history_data_internal()

    magnetic_value = data['magnetic_value']
    defects = data['defects']
    today_data = data['today_data']
    entrys = data.get('historical_data', [])
    # Filter out Probability > 0.04 data
    issues = [row for row in today_data if row['Probability'] > 0.04]

    # Filter historical data by meter
    historical_data = filter_problems_data(entrys,meter)
    print(historical_data)
    if request.method == 'POST':
        selected_meter = request.form.get('selected_meter')
        # Filter historical data by selected meter
        historical_data = filter_historical_data(entrys,selected_meter)

        # Return JSON response
        return jsonify({
            'selected_meter': selected_meter,
            'data_hp': historical_data,
            'magnetic_value': magnetic_value,
            'issues': issues,
            'defects': defects,
        })

    # Render the template with the filtered data
    return render_template('healthiness_prediction.html', defects=defects, issues=issues, data_hp=historical_data,
                           magnetic_value=magnetic_value, meter=meter)

@app.route('/get_prediction', methods=['POST'])
def get_prediction():
    data = request.get_json()  # 获取前端传递的JSON数据
    day = data.get('day')  # 提取预测天数参数
    meter = data.get('meter') # 提取meter参数
    combined_data = get_combined_data(day, meter)
    print(combined_data)
    # todo:historical_data是固定的，有没有什么方法可以在meter不变时暂时保存数据，不用每次都去请求一次

    return jsonify(combined_data)


@app.route('/problems/', methods=['GET', 'POST'])
def problems():
    # 合并 API 请求获取所有数据
    try:
        data = get_problems_data_internal()
    except requests.RequestException as e:
        return jsonify({'error': 'Failed to retrieve data from API', 'details': str(e)}), 500

    magnetic_value = data.get('magnetic_value', [])
    defects = data.get('defects', [])
    today_data = data.get('today_data', [])
    historical_data = data.get('historical_data', [])

    # 筛选出 Probability > 0.04 的数据
    issues = [row for row in today_data if row.get('Probability', 0) > 0.04]

    # 如果是 POST 请求，处理选择的 meter
    if request.method == 'POST':
        selected_meter = request.form.get('selected_meter')
        meter_historical_data = filter_problems_data(historical_data,selected_meter)

        return jsonify({
            'selected_meter': selected_meter,
            'historical_data': meter_historical_data,
            'magnetic_value': magnetic_value,
            'issues': issues,
            'defects': defects,
        })

    # 默认显示第一个 Probability < 0.8 的 meter
    if issues:
        selected_meter = issues[0]['meter']
        historical_data_init = filter_problems_data(historical_data,selected_meter)
    else:
        return jsonify({'message': 'No issues found.'})

    return render_template(
        'problems.html',
        selected_meter=selected_meter,
        today_data=today_data,
        historical_data=historical_data_init,
        magnetic_value=magnetic_value,
        issues=issues,
        defects=defects
    )


@app.route('/get_image', methods=['GET'])
def get_image():
    meter = request.args.get('meter')
    date = datetime.today().date().strftime('%Y-%m-%d')


    try:
        # 解析日期
        date = datetime.strptime(date, '%Y-%m-%d').date()

        # 从数据库中查询图片数据
        image_data = session.query(PictureDefect.picture_data).filter_by(position=meter, date=date).first()

        if image_data:
            # 设置响应头
            response = make_response(image_data[0])
            response.headers.set('Content-Type', 'image/jpeg')  # 根据实际图片类型调整
            return response
        else:
            return "<h1>Image not found</h1>", 404

    except Exception as e:
        print(e)
        return "<h1>Internal Server Error</h1>", 500


# FFmpeg 命令
def start_ffmpeg_in_new_cmd(command):
    """
    在新的 CMD 窗口中运行 FFmpeg 命令，并返回 Popen 进程对象。
    """
    global ffmpeg_process
    try:
        # 修改为使用 && exit 来确保 FFmpeg 结束时关闭 CMD 窗口
        ffmpeg_command = f"start cmd /k \"{command} && exit\""
        # 启动 FFmpeg 进程
        ffmpeg_process = subprocess.Popen(ffmpeg_command, shell=True)
        print("FFmpeg is working in CMD.")
    except Exception as e:
        print("cannot start FFmpeg:", e)



def stop_ffmpeg_process():
    """
    停止当前的 FFmpeg 进程，并确保关闭对应的 CMD 窗口。
    """
    global ffmpeg_process
    if ffmpeg_process:
        try:
            ffmpeg_process.terminate()  # 终止当前 FFmpeg 进程
            ffmpeg_process.wait()  # 等待进程结束
            ffmpeg_process = None
            print("FFmpeg stopped.")
        except Exception as e:
            print(f"Error while stopping FFmpeg process: {e}")
    else:
        print("No FFmpeg process to stop.")


# 连接 RTSP 流
def connect_to_rtsp_stream():
    global cap, rtsp_url, is_connected
    retries = 0
    # 确保 rtsp_url 不为空
    if not rtsp_url:
        print("stream is closed")
        time.sleep(RETRY_INTERVAL)
        return False

    while retries < MAX_RETRIES:
        cap = cv2.VideoCapture(rtsp_url)
        if cap.isOpened():
            is_connected = True  # 成功连接后，标记为已连接
            print(f"Connected to RTSP stream: {rtsp_url}")
            # 启动新的 FFmpeg 命令
            ffmpeg_command = (
                f"ffmpeg -i {rtsp_url} -c:v copy -an -f segment "
                f"-segment_time 60 -reset_timestamps 1 -strftime 1 "
                f"outputvideo/output_%Y-%m-%d_%H-%M-%S.mp4"
            )
            #start_ffmpeg_in_new_cmd(ffmpeg_command)  # 启动新的 FFmpeg 进程
            return True
        else:
            print(f"Failed to connect to {rtsp_url}, retrying in {RETRY_INTERVAL} seconds...")
            time.sleep(RETRY_INTERVAL)
            retries += 1
    print(f"Failed to connect to RTSP stream after {MAX_RETRIES} attempts.")
    return False


# 生成空帧
def empty_frame():
    black_frame = np.zeros((480, 640, 3), dtype=np.uint8)  # 创建黑色帧，大小为 640x480
    _, buffer = cv2.imencode('.jpg', black_frame)
    frame_bytes = buffer.tobytes()
    return (b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


def datetime_cv():
    now = datetime.now()
    dt_string = now.strftime("%Y%m%d_%H%M%S")
    return dt_string


# 视频流生成器
def generate_frames():
    global cap, rtsp_url, is_connected, change

    img_index = 0
    read_fail_counter = 0  # 用于记录连续读取失败的次数
    MAX_READ_RETRIES = 5  # 可以根据需求调整此值
    READ_RETRY_INTERVAL = 0.5  # 每次重试前等待的时间，单位：秒

    while True:
        if change:
            # 如果流地址变化，关闭当前流和 FFmpeg 进程并重新连接
            if cap:
                cap.release()
                print("Closed previous video stream.")
            stop_ffmpeg_process()  # 关闭之前的 FFmpeg 进程
            change = False  # 重置切换标志

            # 重新连接 RTSP 流
            if not connect_to_rtsp_stream():
                yield empty_frame()  # 返回空帧，表示流不可用
                continue

            # 启动新的 FFmpeg 命令
            ffmpeg_command = (
                f"ffmpeg -i {rtsp_url} -c:v copy -an -f segment "
                f"-segment_time 60 -reset_timestamps 1 -strftime 1 "
                f"output_%Y-%m-%d_%H-%M-%S.mp4"
            )
            #start_ffmpeg_in_new_cmd(ffmpeg_command)  # 启动新的 FFmpeg 进程

        if not is_connected:
            # 如果没有连接流，则尝试连接
            if not connect_to_rtsp_stream():
                yield empty_frame()  # 返回空帧，表示流不可用
                continue

        if cap and rtsp_url:
            try:
                ret, frame = cap.read()
                if not ret:
                    # 未能成功读取帧，增加计数并等待后重试
                    read_fail_counter += 1
                    print(f"No frame read. Retrying... (Attempt {read_fail_counter}/{MAX_READ_RETRIES})")

                    if read_fail_counter < MAX_READ_RETRIES:
                        # 尚未达到最大重试次数，等待一段时间后继续读取
                        time.sleep(READ_RETRY_INTERVAL)
                        continue
                    else:
                        # 已达到最大重试次数，可能是流中断，需要重连
                        print("Failed to read frame after multiple attempts. Attempting to reconnect...")
                        yield empty_frame()
                        connect_to_rtsp_stream()
                        read_fail_counter = 0  # 重置计数器
                        continue

                    # 如果成功读取到帧，重置计数器
                read_fail_counter = 0

                # YOLO 推理
                results = model.predict(frame, conf=0.3, imgsz=640, show_conf=False)

                # 绘制检测结果
                for result in results:
                    annotated_frame = result.plot()
                    if result.boxes.conf.nelement() != 0:
                        relative_path_folder_load_path = "1_data/cv_result"
                        folder_load_path = os.path.abspath(relative_path_folder_load_path)
                        merged_path = os.path.join(folder_load_path, f"annotated_frame_{img_index}_{datetime_cv()}.jpg")
                        img_index += 1
                        cv2.imwrite(merged_path, annotated_frame)

                # 编码帧为 JPEG 格式
                _, buffer = cv2.imencode('.jpg', annotated_frame)
                frame_bytes = buffer.tobytes()

                # 返回帧数据作为 MJPEG 流
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

            except Exception as e:
                print(f"Error in frame processing: {e}")
                yield empty_frame()  # 如果处理帧时出现错误，返回空帧
                connect_to_rtsp_stream()  # 尝试重新连接流


# 路由：视频流
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# 路由：更新 RTSP 流地址
@app.route('/update_rtsp_url', methods=['POST'])
def update_rtsp_url():
    global rtsp_url, cap, ffmpeg_process, is_connected, change

    # 获取请求中的新 RTSP URL
    new_rtsp_url = request.json.get('rtsp_url', None)

    if new_rtsp_url:
        # 更新 RTSP URL 并设置 change 标志为 True
        rtsp_url = new_rtsp_url
        change = True  # 设置流地址改变标志

    else:
        # 关闭流和 FFmpeg 进程
        if cap:
            cap.release()
            cap = None
        stop_ffmpeg_process()  # 关闭 FFmpeg 进程
        rtsp_url = None
        is_connected = False  # 断开连接
        print("Closed video stream.")

    return {'status': 'success'}

#每秒返回缆线当前位置
@app.route('/get_latest_data')
def get_latest_data():
    session = Session()
    try:
        # 获取最新的 Event0 数据
        latest_event = session.query(Event0.speed, Event0.position).order_by(Event0.id.desc()).first()

        if latest_event:
            current_speed = latest_event.speed
            current_position = latest_event.position

            # 更新队列
            with queue_lock:
                speed_queue.append(current_speed)
                # 计算返回的速度值
                if current_speed == 0:
                    return_speed = 0
                else:
                    # 过滤掉速度为0的值
                    non_zero_speeds = [s for s in speed_queue if s != 0]
                    if non_zero_speeds:
                        return_speed = sum(non_zero_speeds) / len(non_zero_speeds)
                    else:
                        return_speed = 0  # 如果队列中全是0，则返回0

            # 仅对速度进行四舍五入保留2位小数
            return_speed = round(return_speed, 2)

            # 返回计算后的速度和位置
            return jsonify({
                'speed': return_speed,
                'position': current_position
            })
        else:
            return jsonify({'error': 'No data available'}), 404
    except Exception as e:
        # 在实际应用中，应记录异常日志
        return jsonify({'error': 'Server error'}), 500
    finally:
        session.close()


if __name__ == '__main__':
    try:
        # 启动 Flask 服务
        print("启动 Flask 服务...")
        app.run(host='0.0.0.0', port=5000)


    except KeyboardInterrupt:
        print("检测到退出信号，正在关闭...")
    finally:
        # 释放 RTSP 资源
        cap.release()
        print("资源释放完成，程序退出。")
