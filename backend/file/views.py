from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from file.serializers import FileSerializer, InsuranceSerializer
from file.models import Insurance
from file.utils import ReadingExcelFile, GenrateExcelFile
from django.db import transaction
from django.http import FileResponse, HttpResponse


class FileView(APIView):
    
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, requests):
        return Response({'file': 'runing'}, status=status.HTTP_200_OK)
    
    def post(self, request, *args, **kwargs):
        data = request.data
        user_instance = request.user

        serializer = FileSerializer(data=data)
        if serializer.is_valid():
            file_data = serializer.save(
                created_by = user_instance,
                updated_by = user_instance,
            )
            read_file = ReadingExcelFile(file_data.get('file_path', None))
            list_of_dataframs = []
            sheet_names = read_file.get_sheet_list()
            for sheet in sheet_names:
                df = read_file.remove_nan_row(sheet)
                file_info = read_file.extract_file_info(df)
                year = file_info.get('year', '')
                month = file_info.get('month', '').capitalize()[:3]
                fixing_columns = read_file.fixing_columns(df)
                cleaning_file = read_file.cleaning_file(fixing_columns)
                list_of_dataframs.append(cleaning_file)
            extract_data = read_file.extract_data(list_of_dataframs, year, month)
            extract_data = read_file.group_records(extract_data)
            instances_ = []
            insurance_seralizer = InsuranceSerializer(data=extract_data, many=True)
            if insurance_seralizer.is_valid():
                with transaction.atomic():
                    validated_data = insurance_seralizer.validated_data

                    for item in validated_data:
                        item['file'] = file_data.get('instance')
                        item['created_by'] = user_instance
                        item['updated_by'] = user_instance
                        
                        instance = Insurance(**item)
                        instances_.append(instance)
            Insurance.objects.bulk_create(instances_)

            created_serializer = InsuranceSerializer(instances_, many=True)
            return Response({'records': created_serializer.data, 'download_id': file_data.get('instance').file_id , 'status': 'success'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DownloadAPIView(APIView):

    def get(self, request, pk):
        records = Insurance.objects.download_file(pk)
        if not records:
            return Response({'message': 'No records found'}, status=status.HTTP_404_NOT_FOUND)
        
        excel_genrator = GenrateExcelFile(records)
        output = excel_genrator.write_data()
        response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=report.xlsx'
        
        return response

        # response = FileResponse(output, as_attachment=True, filename='report.xlsx')
        # return response
        # return FileResponse(file, as_attachment=True, filename='report.xlsx')
        