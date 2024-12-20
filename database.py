from sqlalchemy.dialects.mysql import BLOB
from sqlalchemy import create_engine, Column, String, Float, Date, Time, Integer, LargeBinary,Index, cast, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from werkzeug.security import generate_password_hash, check_password_hash
# 配置数据库连接
DATABASE_URL = 'mysql+pymysql://root:123456@localhost/peaktram'

# 创建数据库引擎，并配置连接池
engine = create_engine(
    DATABASE_URL,
    pool_recycle=3600,  # 在一定时间后回收连接，避免长时间空闲导致的问题
    pool_size=10,  # 连接池的大小，可以根据需求调整
    max_overflow=20,  # 在连接池满的情况下，可以额外创建的连接数量
    pool_timeout=30  # 获取连接的超时时间
)

# 声明基类
Base = declarative_base()






class PictureData(Base):
    __tablename__ = 'picture_cv'
    meter = Column(Float, primary_key=True)
    date = Column(Date, primary_key=True)
    picture = Column(BLOB, nullable=False)


class Defect(Base):
    __tablename__ = 'defect'
    meter = Column(Float, primary_key=True)
    date = Column(Date, primary_key=True)
    possible_deffect = Column(String, nullable=False)

class MagneticData(Base):
    __tablename__ = 'magnetic_value'
    date = Column(Date, primary_key=True)
    #recId = Column(Integer, primary_key=True)
    time = Column(Time, nullable=True)
    position = Column(Float, primary_key=True)
    speed = Column(Float, nullable=True)
    sensor1 = Column(Integer)
    sensor2 = Column(Integer)
    sensor3 = Column(Integer)
    sensor4 = Column(Integer)
    sensor5 = Column(Integer)
    sensor6 = Column(Integer)
    LMA_value = Column(Float)  # LMA值，默认为0
    diameter = Column(Float)  # 直径，默认为50.5

# 定义 health_score 表结构
class LMAPrediction(Base):
    __tablename__ = 'lma_prediction'
    date = Column(Date, primary_key=True)
    position = Column(Float, primary_key=True)
    LMA_day_1 = Column(Float, nullable=True)  # 预测第1天的值
    LMA_day_2 = Column(Float, nullable=True)  # 预测第2天的值
    LMA_day_3 = Column(Float, nullable=True)  # 预测第3天的值
    LMA_day_4 = Column(Float, nullable=True)  # 预测第4天的值

class Event5(Base):
    __tablename__ = 'event_5'
    recId = Column(Integer, primary_key=True)
    date = Column(Date, primary_key=True)
    time = Column(Time)
    position = Column(Float, primary_key=True)
    LMA_value = Column(Float)
    diameter = Column(Float)
    defect_degree = Column(Integer)
    defect_type = Column(Integer)

# 定义 picture_defect 表结构
class PictureDefect(Base):
    __tablename__ = 'picture_defect'
    date = Column(Date, primary_key=True)
    position = Column(Float, primary_key=True)
    picture_data = Column(LargeBinary)
    issue = Column(String(255))


# 用户模型
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(150), unique=True, nullable=False)
    password = Column(String(200), nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


# 定义模型类
class Event0(Base):
    __tablename__ = 'event_0'  # 表名为 event_0

    id = Column(Integer, primary_key=True, autoincrement=True)  # 主键，自增
    date = Column(Date, nullable=False)  # 存储数据接收时间
    time = Column(Time, nullable=True)
    speed = Column(Float, nullable=False)  # 实时速度
    position = Column(Float, nullable=False)  # 实时位置

    # 创建单字段索引
    __table_args__ = (
        Index('ix_event_0_date', 'date'),  # 针对 date 创建索引
    )

class RopeDetails(Base):
    __tablename__ = 'rope_details'

    sn = Column(String(50), primary_key=True)
    node = Column(String(50), primary_key=True)
    time = Column(Date, primary_key=True)
    ropeLen = Column(Float)
    ropeCnt = Column(Integer)
    ropeManuf = Column(String(100))
    ropeSpecific = Column(String(100))
    ropeDm = Column(Integer)
    ropeThigh = Column(Integer)
    ropeSilk = Column(Integer)
    ropeMaterial = Column(String(50))  # 碳素钢、不锈钢
    ropeCore = Column(String(50))  # 纤维芯、钢芯
    ropeSurface = Column(String(50))  # 光面、镀锌、涂塑、磷化
    ropeTwist = Column(String(10))  # zZ、sS、zS、sZ
    ropeFknMin = Column(Integer)
    ropeFknFact = Column(Integer)
    ropeStructure = Column(String(255))
    ropeUsedate = Column(String(20))  # 可以修改为 Date 类型，取决于数据格式

# 创建数据库会话，并使用 scoped_session 以线程安全的方式管理会话
SessionFactory = sessionmaker(bind=engine)
Session = scoped_session(SessionFactory)



session = Session()

# 初始化数据库
def init_db():
    Base.metadata.create_all(engine)
