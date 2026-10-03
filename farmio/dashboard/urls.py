from django.urls import path

from farmio.dashboard import report_views

from . import views

app_name = "dashboard"

urlpatterns = [
    path("buyer/", views.BuyerDashboardView.as_view(), name="buyer"),
    path("producer/", views.ProducerDashboardView.as_view(), name="producer"),
    path("admin/", views.AdminDashboardView.as_view(), name="admin"),
    path(
        "admin/reports/pdf/",
        report_views.AdminReportPdfView.as_view(),
        name="report-pdf",
    ),
    path(
        "admin/reports/excel/",
        report_views.AdminReportExcelView.as_view(),
        name="report-excel",
    ),
]
