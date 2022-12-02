from typing import List

from app.client import weather
from app.dependencies import get_db
from app.schemas import *  # noqa: F401, F403
from app.schemas import (AlertsResponse, CurrentWeatherResponse, RiskEvent,
                         RiskLevel, RiskResponse, SingleWeatherResponse,
                         ImmediateForecastResponse)
from app.utils import (convert, convert_epoch_to_datetime, geocode_address,
                       get_immediate_weather_api_call, get_location_obj,
                       get_weather_forecast,
                       immediate_weather_api_call_tommorrow, reverse_geocode,
                       weather_api_call)
from fastapi import APIRouter, Depends, HTTPException, status
from schemas import (AlertsResponse, CurrentWeatherResponse,
                     ImmediateForecastResponse, SingleWeatherResponse)
from sqlalchemy.orm import Session
from utils.client import weather
from utils.general import (convert, convert_epoch_to_datetime, geocode_address,
                           get_immediate_weather_api_call, get_location_obj,
                           get_weather_forecast,
                           immediate_weather_api_call_tommorrow,
                           reverse_geocode, weather_api_call, get_risk)

router = APIRouter(
    prefix="/weather",
    tags=['weather']
)


@router.get('/forecasts', response_model=List[SingleWeatherResponse])
async def weather_forcasts(lat: float, lon: float):
    """Get weather forecast for next 10 steps"""
    try:
        weather_forecasts_data = get_weather_forecast(lat, lon)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can't retrive weather data for this location"
        )

    results = []

    for forcast in weather_forecasts_data:
        data = convert_epoch_to_datetime(forcast.get('dt'))
        data['main'] = forcast['weather'][0]['main']
        data['description'] = forcast['weather'][0]['description']
        results.append(data)

    return results


@router.get('/current', response_model=CurrentWeatherResponse)
async def get_current_weather(address: str):
    """Get current weather for a given address

    :param address: Address to get weather for
    :type address: str
    :raises HTTPException: If address is not valid or not found
    :return: Current weather for the address
    :rtype: CurrentWeatherResponse
    """

    geo_address = geocode_address(address)
    lat, lon = geo_address['lat'], geo_address['lon']

    weather_data = weather_api_call(lon, lat)

    return {
        "city": geo_address['city'],
        "state": geo_address['state'],
        'main': weather_data['main'],
        'description': weather_data['description'],
        **convert_epoch_to_datetime(weather_data['dt'])
    }


@router.get("/forecasts/immediate", response_model=ImmediateForecastResponse)
async def immediate_weather_forecast(lat: float = None, lng: float = None):

    if lat is None and lng is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="invalid longitute and latitude"
        )
    result = get_immediate_weather_api_call(lat, lng)

    return result


@router.get("/forecasts/tomorrow")
async def weather_data(lat: float, lon: float):
    try:
        result = weather(lat, lon)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can't retrive weather data for this location"
        )

    epoch = convert()

    starting_point = None

    for index, _data in enumerate(result):
        if _data['dt'] >= epoch:
            starting_point = index
            break

    if starting_point is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Weather condition not found, Please try again"
        )
    result = result[starting_point:10]
    bus = []
    for forecast in result:
        data = convert_epoch_to_datetime(forecast.get('dt'))
        data['main'] = forecast['weather'][0]['main']
        data['description'] = forecast['weather'][0]['description']
        bus.append(data)
    return bus


@router.get('/forecasts/tomorrow/immediate')
async def get_tommorrows_weather(lat: float, lon: float):

    if lat is None and lon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="invalid longitute and latitude"
        )

    try:
        tommorows_weather = immediate_weather_api_call_tommorrow(
            lon, lat)  # returns a dictionary
        return tommorows_weather

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can't retrive weather data for this location"
        )


@router.get('/alerts/list', response_model=List[AlertsResponse])
def get_alert_list(lon: float, lat: float, db: Session = Depends(get_db)):

    latlng = reverse_geocode(lat, lon)
    city = latlng.get('city')
    state = latlng.get('state')

    loc_obj = get_location_obj(db, city, state)

    data = []

    if loc_obj is not None:
        for mydata in loc_obj.alerts:

            date_time = convert_epoch_to_datetime(mydata.end)

            alert_instance = {
                'event': mydata.event,
                'message': mydata.message,
                'date': date_time['date'],
                'time': date_time['time']
            }

            data.append(alert_instance)

    return data


@router.get('/risk', response_model=List[RiskResponse])
async def get_location_weather_risk(lat: float, lon: float):

    return [
        {
            "risk": RiskEvent.FLOOD,
            "level": RiskLevel.HIGH,
        },
        {
            "risk": RiskEvent.SUNBURN,
            "level": RiskLevel.LOW,
        },
        {
            "risk": RiskEvent.DUST,
            "level": RiskLevel.MODERATE,
        },
        {
            "risk": RiskEvent.FOG,
            "level": RiskLevel.EXTREME,
        }
    ]

@router.get('/forcast/extended')
async def get_extended_forecast(lat: float, lon: float):
    
    # API call
    
    req = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=weathercode&hourly=precipitation&hourly=temperature_2m&timezone=GMT&current_weather=true"
    
    res = dict(requests.get(req).json())
    address = reverse_geocoding(lat, lon)
    city = address[0]['name']
    state = address[0]['state']
    country = address[0]['country']
    
    main = res['current_weather']['weathercode']
    datetime = res['current_weather']['time']
    hourly_timestamps = res['hourly']['time']
    
    # get the current time index to be used in other parameters
    time_index : int = hourly_timestamps.index(datetime)
    
    weather_code = res['hourly']['weathercode']
    weather_code[time_index]
    temperature = res['hourly']['temperature_2m'][time_index]
    
    precipitation = res['hourly']['precipitation'][time_index]
    

    match = weather_code[time_index]

    for i in range(time_index, len(weather_code)):
    
        if match != weather_code[i]:
            break 
    
    end_datetime = hourly_timestamps[i]
    risk = get_risk(temperature, precipitation)
    
    current = {
        "main" : weather_code_transcribe(main),
        "datetime": datetime.replace("T", " "),
        "end_datetime": end_datetime.replace("T", " "),
        "risk": risk
    } 

    todays_timeline= []
    time_line = {
        main: weather_code_transcribe(main),
        "datetime": datetime,
        "risk": risk
    }

    todays_timeline.append(time_line)
    
    result = {
        
        "city": city,
        "state": state,
        "country": country,
        "current": current,
        "todays_timeline": todays_timeline

            }
    return result   
    
    

    
    

        
