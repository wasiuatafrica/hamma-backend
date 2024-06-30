import json
import boto3
from django.core.management.base import BaseCommand
from concurrent.futures import ThreadPoolExecutor
from execution.tasks import update_live_1m_lambda
from portfolio.models import Stock


class Command(BaseCommand):
    help = 'Trigger the gen_data_test Lambda function 200 times concurrently'

    def handle(self, *args, **kwargs):
        # update_live_1m_lambda()
        # stocks = [stock.symbol for stock in Stock.objects.filter(active=True).order_by('symbol')]
        # print(stocks)
        stocks = ['CHAMS', 'CHELLARAM', 'CILEASING', 'CONOIL', 'CORNERST', 'CUSTODIAN', 'CUTIX', 'CWG', 'DAARCOMM', 'DANGCEM', 
                  'DANGSUGAR', 'DEAPCAP', 'DUNLOP', 'EKOCORP', 'ELLAHLAKES', 'ENAMELWA', 'ETERNA', 'ETI', 'ETRANZACT', 'EUNISELL', 'FBNH', 'FCMB', 
                  'FIDELITYBK', 'FIDSON', 'FLOURMILL', 'FTNCOCOA', 'GEREGU', 'GOLDBREW', 'GOLDINSURE', 'GTCO', 'GUINEAINS', 'GUINNESS', 'HONYFLOUR', 
                  'IKEJAHOTEL', 'IMG', 'INFINITY', 'INTBREW', 'INTENEGINS', 'JAIZBANK', 'JAPAULGOLD', 'JBERGER', 'JOHNHOLT', 'JULI', 'LASACO', 
                  'LEARNAFRCA', 'LINKASSURE', 'LIVESTOCK', 'LIVINGTRUST', 'MANSARD', 'MAYBAKER', 'MBENEFIT', 'MCNICHOLS', 'MEDVIEWAIR', 'MEYER', 
                  'MORISON', 'MRS', 'MTNN', 'MULTITREX', 'MULTIVERSE', 'NAHCO', 'NASCON', 'NB', 'NCR', 'NEIMETH', 'NEM', 'NESTLE', 'NGXGROUP', 
                  'NIDF', 'NIGERINS', 'NNFM', 'NOTORE', 'NPFMCRFBK', 'NSLTECH', 'OANDO', 'OKOMUOIL', 'OMATEK', 'PHARMDEKO', 'PREMPAINTS', 'PRESCO', 
                  'PRESTIGE', 'PZ', 'RAKUNITY', 'REDSTAREX', 'REGALINS', 'RESORTSAL', 'RONCHESS', 'ROYALEX', 'RTBRISCOE', 'SCOA', 'SEPLAT', 
                  'SFSREIT', 'SKYAVN', 'SMURFIT', 'SOVRENINS', 'STACO', 'STANBIC', 'STDINSURE', 'STERLINGNG', 'SUNUASSUR', 'TANTALIZER', 
                  'THOMASWY', 'TIP', 'TOTAL', 'TOURIST', 'TRANSCOHOT', 'TRANSCORP', 'TRANSEXPR', 'TRIPPLEG', 'UACN', 'UBA', 'UCAP', 'UHOMREIT', 
                  'UNHOMES', 'UNILEVER', 'UNIONDICON', 'UNITYBNK', 'UNIVINSURE', 'UPDC', 'UPDCREIT', 'UPL', 'VANLEER', 'VERITASKAP', 'VFDGROUP', 
                  'VITAFOAM', 'WAPCO', 'WAPIC', 'WEMABANK', 'ZENITHBANK']
        
        lambda_client = boto3.client('lambda',region_name='eu-north-1')
        
        def invoke_lambda(symbol):
            event_payload = {
                'symbol': symbol,
            }
            response = lambda_client.invoke(
                        # FunctionName='gen_data_test',
                        FunctionName='update_live_1m',
                        InvocationType='Event',  # Async invocation
                        Payload=json.dumps(event_payload)
                    )
            print(f"{symbol} triggerred")
            
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(invoke_lambda, symbol) for symbol in stocks]

            for future in futures:
                # This will block until each future is done and will raise exceptions if any occurred
                future.result()
        print('all done')