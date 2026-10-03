from __future__ import annotations

from io import BytesIO

import xlsxwriter
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView
from weasyprint import HTML

from farmio.catalog.models import Product
from farmio.dashboard.services import build_admin_dashboard_data
from farmio.orders.models import Order
from farmio.reviews.models import Review
from farmio.reviews.models import ReviewModerationStatus
from farmio.users.permissions import AdminRequiredMixin


class AdminReportMixin(LoginRequiredMixin, AdminRequiredMixin):
    def get_report_data(self):
        return build_admin_dashboard_data()


class AdminReportPdfView(AdminReportMixin, TemplateView):
    template_name = "dashboard/reports/admin_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["report"] = self.get_report_data()
        return context

    def render_to_response(self, context, **response_kwargs):
        html = render_to_string(self.template_name, context, request=self.request)
        pdf = HTML(
            string=html,
            base_url=self.request.build_absolute_uri("/"),
        ).write_pdf()
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            'attachment; filename="farmio-admin-report.pdf"'
        )
        return response


class AdminReportExcelView(AdminReportMixin, View):
    def get(self, request, *args, **kwargs):
        report = self.get_report_data()
        output = BytesIO()
        workbook = xlsxwriter.Workbook(
            output,
            {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False},
        )
        title_format = workbook.add_format(
            {"bold": True, "font_size": 16, "font_color": "#14532d"},
        )
        header_format = workbook.add_format(
            {"bold": True, "bg_color": "#166534", "font_color": "#FFFFFF"},
        )
        date_format = workbook.add_format({"num_format": "yyyy-mm-dd hh:mm"})

        summary = workbook.add_worksheet("Résumé")
        summary.write(0, 0, "Rapport d'administration Farmio", title_format)
        summary.write(1, 0, "Généré le")
        summary.write_datetime(
            1,
            1,
            report["generated_at"].replace(tzinfo=None),
            date_format,
        )
        for row, (label, value) in enumerate(
            [
                (_("Utilisateurs actifs"), report["users_count"]),
                (_("Acheteurs actifs"), report["buyers_count"]),
                (_("Producteurs actifs"), report["producers_count"]),
                (_("Produits"), report["products_count"]),
                (_("Commandes"), report["orders_count"]),
                (_("Commandes terminées"), report["completed_orders_count"]),
                (_("Avis approuvés"), report["reviews_count"]),
                (_("Avis en attente"), report["reviews_pending_count"]),
                (_("Note moyenne"), report["reviews_average"] or 0),
            ],
            start=3,
        ):
            summary.write(row, 0, str(label))
            summary.write(row, 1, value)
        summary.write(
            14,
            0,
            "Paiements réussis - montants séparés par devise",
            header_format,
        )
        summary.write_row(15, 0, ["Devise", "Montant", "Nombre"], header_format)
        for row, currency_total in enumerate(report["revenue_by_currency"], start=16):
            summary.write(row, 0, currency_total["amount_currency"])
            summary.write(row, 1, currency_total["total"] or 0)
            summary.write(row, 2, currency_total["payments"])
        summary.set_column("A:A", 44)
        summary.set_column("B:C", 22)

        orders = workbook.add_worksheet("Commandes")
        orders.write_row(
            0,
            0,
            [
                "Référence",
                "Acheteur",
                "Producteur",
                "Statut",
                "Montant",
                "Devise",
                "Créée le",
            ],
            header_format,
        )
        for row, order in enumerate(
            Order.objects.filter(is_deleted=False)
            .select_related("buyer", "producer")
            .iterator(chunk_size=500),
            start=1,
        ):
            orders.write_row(
                row,
                0,
                [
                    order.reference,
                    order.buyer.email,
                    order.producer.email,
                    order.get_status_display(),
                    float(order.total_amount.amount),
                    order.total_amount.currency.code,
                ],
            )
            orders.write_datetime(
                row,
                6,
                order.created_at.replace(tzinfo=None),
                date_format,
            )
        orders.set_column("A:A", 18)
        orders.set_column("B:C", 32)
        orders.set_column("D:F", 18)
        orders.set_column("G:G", 22)

        products = workbook.add_worksheet("Produits")
        products.write_row(
            0,
            0,
            [
                "Produit",
                "Producteur",
                "Catégorie",
                "Statut",
                "Prix",
                "Devise",
                "Stock",
            ],
            header_format,
        )
        for row, product in enumerate(
            Product.objects.filter(is_deleted=False)
            .select_related("producer", "category")
            .iterator(chunk_size=500),
            start=1,
        ):
            products.write_row(
                row,
                0,
                [
                    product.name,
                    product.producer.email,
                    product.category.name,
                    product.get_status_display(),
                    float(product.price.amount),
                    product.price.currency.code,
                    product.quantity,
                ],
            )
        products.set_column("A:A", 30)
        products.set_column("B:C", 32)
        products.set_column("D:G", 18)

        reviews = workbook.add_worksheet("Avis approuvés")
        reviews.write_row(
            0,
            0,
            ["Commande", "Acheteur", "Producteur", "Note", "Commentaire", "Date"],
            header_format,
        )
        for row, review in enumerate(
            Review.objects.filter(
                is_deleted=False,
                moderation__status=ReviewModerationStatus.APPROVED,
            )
            .select_related("buyer", "producer", "order")
            .iterator(chunk_size=500),
            start=1,
        ):
            reviews.write_row(
                row,
                0,
                [
                    review.order.reference,
                    review.buyer.email,
                    review.producer.email,
                    review.rating,
                    review.comment,
                ],
            )
            reviews.write_datetime(
                row,
                5,
                review.created_at.replace(tzinfo=None),
                date_format,
            )
        reviews.set_column("A:A", 18)
        reviews.set_column("B:C", 32)
        reviews.set_column("D:D", 10)
        reviews.set_column("E:E", 64)
        reviews.set_column("F:F", 22)

        workbook.close()
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            'attachment; filename="farmio-admin-report.xlsx"'
        )
        response["Last-Modified"] = timezone.now().strftime(
            "%a, %d %b %Y %H:%M:%S GMT",
        )
        return response
