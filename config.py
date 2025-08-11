# Configuration file for Interest Calculator Application

# Application Settings
APP_NAME = "Interest Calculator"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Interest Calculator Team"

# Database Settings
DATABASE_NAME = "interest_calculations.db"
MAX_HISTORY_ITEMS = 20

# Default Values
DEFAULT_TIME_UNIT = "years"
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# UI Settings
WINDOW_WIDTH = 700
WINDOW_HEIGHT = 500
PADDING = 20

# Calculation Settings
DAYS_PER_YEAR = 365
MONTHS_PER_YEAR = 12

# Validation Settings
MIN_PRINCIPAL = 0.01
MIN_RATE = 0.0
MIN_TIME = 0.01
MAX_RATE = 1000.0  # 1000% maximum rate
MAX_TIME = 1000.0  # 1000 years maximum time
