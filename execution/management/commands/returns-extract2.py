# Import necessary libraries
import openpyxl
from django.core.management.base import BaseCommand
from execution.models import DemoDailyReturns, DemoCumulativeReturns

class Command(BaseCommand):
    help = 'Export DemoDailyReturns data to xlsx file'

    def handle(self, *args, **kwargs):
        # Query DemoDailyReturns data
        # data = DemoDailyReturns.objects.all()
        data = DemoCumulativeReturns.objects.filter(user__email='ayo@ft9ja.com')
        print('lenght', len(data)  )
        # print(data)
        # data = DemoDailyReturns.objects.filter(user__email='ayo@atafrica')

        # Create a new Excel workbook
        wb = openpyxl.Workbook()
        ws = wb.active

        # Write headers
        headers = ['User', 'Portfolio Returns', 'Market Returns', 'NGX Price', 'Created']
        for col_num, header in enumerate(headers, start=1):
            ws.cell(row=1, column=col_num, value=header)

        # Write data rows
        for row_num, instance in enumerate(data, start=2):
            ws.cell(row=row_num, column=1, value=instance.user.email)
            ws.cell(row=row_num, column=2, value=instance.portfolio_returns)
            ws.cell(row=row_num, column=3, value=instance.market_returns)
            ws.cell(row=row_num, column=4, value=instance.ngx_price)
            created_naive = instance.created.replace(tzinfo=None)
            ws.cell(row=row_num, column=5, value=created_naive)

        # Save the workbook
        file_path = 'ayo_cumulative_returns.xlsx'  # You can specify your desired file path here
        wb.save(file_path)

        self.stdout.write(self.style.SUCCESS(f'Successfully exported data to {file_path}'))
