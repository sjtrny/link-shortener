from io import BytesIO

import qrcode
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, reverse
from django.utils.html import format_html

from .models import ShortLink


@admin.register(ShortLink)
class ShortLinkAdmin(admin.ModelAdmin):
    list_display = (
        "short_code",
        "target_url",
        "short_url_widget",
        "is_active",
        "created_at",
    )
    search_fields = ("short_code", "target_url")
    list_filter = ("is_active", "created_at")
    readonly_fields = (
        "short_path",
        "short_url_widget",
        "qr_code_preview",
        "created_at",
    )
    fields = (
        "short_code",
        "target_url",
        "is_active",
        "short_path",
        "short_url_widget",
        "qr_code_preview",
        "created_at",
    )

    # QR settings you can tweak
    QR_VERSION = None          # None = auto-fit; use 1-40 to force a version
    QR_ERROR_CORRECTION = qrcode.constants.ERROR_CORRECT_M
    QR_BOX_SIZE = 16           # Increase for higher resolution
    QR_BORDER = 4              # Quiet zone around code
    QR_FILL_COLOR = "black"
    QR_BACK_COLOR = "white"
    QR_PREVIEW_SIZE_PX = 280   # CSS preview size in admin
    QR_DOWNLOAD_FORMAT = "PNG"

    def changelist_view(self, request, extra_context=None):
        self._current_request = request
        return super().changelist_view(request, extra_context=extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        self._current_request = request
        return super().change_view(
            request,
            object_id,
            form_url=form_url,
            extra_context=extra_context,
        )

    def add_view(self, request, form_url="", extra_context=None):
        self._current_request = request
        return super().add_view(
            request,
            form_url=form_url,
            extra_context=extra_context,
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/qr-code/",
                self.admin_site.admin_view(self.qr_code_image_view),
                name="links_shortlink_qr_code",
            ),
        ]
        return custom_urls + urls

    def _build_full_url(self, obj):
        if not obj or not obj.pk:
            return ""

        path = obj.get_absolute_url()
        request = getattr(self, "_current_request", None)

        if request is None:
            return path

        return request.build_absolute_uri(path)

    def _build_qr_image(self, obj):
        url = self._build_full_url(obj)

        qr = qrcode.QRCode(
            version=self.QR_VERSION,
            error_correction=self.QR_ERROR_CORRECTION,
            box_size=self.QR_BOX_SIZE,
            border=self.QR_BORDER,
        )
        qr.add_data(url)
        qr.make(fit=True)

        return qr.make_image(
            fill_color=self.QR_FILL_COLOR,
            back_color=self.QR_BACK_COLOR,
        )

    def _qr_download_filename(self, obj):
        # Example: shortlink-my-custom-code.png
        return f"shortlink-{obj.short_code}.png"

    def short_path(self, obj):
        if not obj or not obj.pk:
            return "Save first"

        path = obj.get_absolute_url()
        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            path,
            path,
        )

    short_path.short_description = "Short path"

    def short_url_widget(self, obj):
        if not obj or not obj.pk:
            return "Save first"

        url = self._build_full_url(obj)
        input_id = f"short-url-{obj.pk}"

        return format_html(
            """
            <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                <input
                    id="{}"
                    type="text"
                    value="{}"
                    readonly
                    style="width: 360px; max-width: 100%;"
                    onclick="this.select();"
                >
                <button
                    type="button"
                    onclick="
                        navigator.clipboard.writeText(document.getElementById('{}').value);
                        this.innerText='Copied!';
                        setTimeout(() => this.innerText='Copy', 1200);
                    "
                >
                    Copy
                </button>
            </div>
            """,
            input_id,
            url,
            input_id,
        )

    short_url_widget.short_description = "Short URL"

    def qr_code_preview(self, obj):
        if not obj or not obj.pk:
            return "Save first"

        image_url = reverse("admin:links_shortlink_qr_code", args=[obj.pk])
        filename = self._qr_download_filename(obj)

        return format_html(
            """
            <div style="display:flex; flex-direction:column; gap:10px;">
                <a href="{0}" target="_blank" download="{1}">
                    <img
                        src="{0}"
                        alt="QR code for {2}"
                        style="
                            width: {3}px;
                            height: {3}px;
                            border: 1px solid #ddd;
                            padding: 8px;
                            background: white;
                        "
                    >
                </a>

                <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                    <a class="button" href="{0}" target="_blank">Open image</a>
                    <a class="button" href="{0}" download="{1}">Download PNG</a>
                </div>

                <div style="font-size: 12px; color: #666;">
                    Click the image to open it, or use Download PNG to save it as {1}
                </div>
            </div>
            """,
            image_url,
            filename,
            self._build_full_url(obj),
            self.QR_PREVIEW_SIZE_PX,
        )

    qr_code_preview.short_description = "QR code"

    def qr_code_image_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            return HttpResponse(status=404)

        img = self._build_qr_image(obj)
        buffer = BytesIO()
        img.save(buffer, format=self.QR_DOWNLOAD_FORMAT)
        content = buffer.getvalue()

        response = HttpResponse(content, content_type="image/png")
        response["Content-Disposition"] = f'inline; filename="{self._qr_download_filename(obj)}"'
        return response