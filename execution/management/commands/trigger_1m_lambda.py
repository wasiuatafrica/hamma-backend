import json
import boto3
from django.core.management.base import BaseCommand
from concurrent.futures import ThreadPoolExecutor


class Command(BaseCommand):
    help = 'Trigger the gen_data_test Lambda function 200 times concurrently'

    def handle(self, *args, **kwargs):

        stocks = ["ABBEYBDS", "ACADEMY", "ACCESSCORP", "AFRIPRUD", "AFRINSURE", "AFROMEDIA", "AIICO", 
          "AIRTELAFRI", "ALEX", "ARBICO", "ASOSAVINGS", "ABCTRANS", "AUSTINLAZ", "MANSARD", "BERGER", 
          "BETAGLAS", "BAPLC", "BUACEMENT", "BUAFOODS", "CILEASING", "CADBURY", "CAP", "CAPOIL", "CAVERTON", 
          "CHAMPION", "CHAMS", "NIDF", "CHELLARAM", "CONOIL", "CHIPLC", "CORNERST", "WAPIC", "CUSTODIAN", 
          "CUTIX", "CWG", "DAARCOMM", "DANGCEM", "DANGSUGAR", "DEAPCAP", "DUNLOP", "ETRANZACT", "ETI", 
          "EKOCORP", "ELLAHLAKES", "ETERNA", "EUNISELL", "FBNH", "FCMB", "FIDELITYBK", "FIDSON", "FLOURMILL",
          "FTNCOCOA", "GEREGU", "GLAXOSMITH", "GOLDBREW", "GOLDINSURE", "VANLEER", "GTCO", "GUINEAINS", 
          "GUINNESS", "HONYFLOUR", "IKEJAHOTEL", "IMG", "INFINITY", "INTBREW", "INTENEGINS", "JAIZBANK", 
          "JAPAULGOLD", "JOHNHOLT", "JULI", "JBERGER", "WAPCO", "LASACO", "LEARNAFRCA", "LINKASSURE", 
          "LIVESTOCK", "LIVINGTRUST", "MAYBAKER", "MCNICHOLS", "MEDVIEWAIR", "MEYER", "MORISON", "MRS", 
          "MTNN", "MULTITREX", "MULTIVERSE", "MBENEFIT", "NNFM", "NASCON", "NCR", "NEIMETH", "NEM", "NESTLE", 
          "NIGERINS", "NESF", "NAHCO", "NB", "ENAMELWA", "NGXGROUP", "NOTORE", "NPFMCRFBK", "OANDO", 
          "OKOMUOIL", "OMATEK", "PZ", "PHARMDEKO", "PREMPAINTS", "PRESCO", "PRESTIGE", "RTBRISCOE", "RAKUNITY", 
          "REDSTAREX", "REGALINS", "RESORTSAL", "RONCHESS", "ROYALEX", "SCOA", "NSLTECH", "SEPLAT", "SFSREIT",
          "SKYAVN", "SMURFIT", "SOVRENINS", "STACO", "STANBIC", "STDINSURE", "STERLINGNG", "SUNUASSUR", 
          "TANTALIZER", "TIP", "THOMASWY", "TOTAL", "TOURIST", "TRANSEXPR", "TRANSCOHOT", "TRANSCORP", 
          "TRIPPLEG", "UACN", "UHOMREIT", "UNILEVER", "UBN", "UNIONDICON", "UNHOMES", "UBA", "UCAP", 
          "UNITYBNK", "UNIVINSURE", "UPL", "UPDC", "UPDCREIT", "VERITASKAP", "VFDGROUP", "VITAFOAM", 
          "WEMABANK", "ZENITHBANK"]
        
        lambda_client = boto3.client('lambda',region_name='eu-north-1')
        
        def invoke_lambda(symbol):
            event_payload = {
                'symbol': symbol,
            }
            response = lambda_client.invoke(
                        FunctionName='fetch_live',
                        InvocationType='Event',  # Async invocation
                        Payload=json.dumps(event_payload)
                    )
            print(f"{symbol} triggerred")
            
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(invoke_lambda, symbol) for symbol in stocks]

            for future in futures:
                future.result()
        print('all done')