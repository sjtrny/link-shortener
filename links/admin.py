from functools import partial, update_wrapper
from io import BytesIO

import qrcode
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.urls import path, reverse
from django.utils.html import format_html

from .models import ShortLink


@admin.register(ShortLink)
class ShortLinkAdmin(admin.ModelAdmin):
    search_fields = ("short_code", "target_url")
    list_filter = ("is_active", "created_at")

    class Media:
        js = ("links/admin.js",)

    # QR settings you can tweak
    QR_VERSION = None          # None = auto-fit; use 1-40 to force a version
    QR_ERROR_CORRECTION = qrcode.constants.ERROR_CORRECT_M
    QR_BOX_SIZE = 16           # Increase for higher resolution
    QR_BORDER = 4              # Quiet zone around code
    QR_FILL_COLOR = "black"
    QR_BACK_COLOR = "white"
    QR_PREVIEW_SIZE_PX = 280   # CSS preview size in admin
    QR_DOWNLOAD_FORMAT = "PNG"

    def get_readonly_fields(self, request, obj=None):
        # Django asks for these fields more than once while building a form.
        # Keep callable identities stable on the request, never on this shared admin.
        if not hasattr(request, "_shortlink_readonly_fields"):
            request._shortlink_readonly_fields = (
                *(
                    update_wrapper(partial(renderer, request), renderer)
                    for renderer in (self.short_path, self.short_url_widget, self.qr_code_preview)
                ),
                "created_at",
            )
        return request._shortlink_readonly_fields

    def get_fields(self, request, obj=None):
        return ("short_code", "target_url", "is_active", *self.get_readonly_fields(request, obj))

    def get_list_display(self, request):
        return (
            "short_code",
            "target_url",
            self.get_readonly_fields(request)[1],
            "is_active",
            "created_at",
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

    def _build_full_url(self, request, obj):
        if not obj or not obj.pk:
            return ""

        path = obj.get_absolute_url()
        if settings.SHORTLINK_BASE_URL:
            return settings.SHORTLINK_BASE_URL + path
        return request.build_absolute_uri(path)

    def _build_qr_image(self, request, obj):
        url = self._build_full_url(request, obj)

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

    def short_path(self, request, obj):
        if not obj or not obj.pk:
            return "Save first"

        path = obj.get_absolute_url()
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            self._build_full_url(request, obj),
            path,
        )

    short_path.short_description = "Short path"

    def short_url_widget(self, request, obj):
        if not obj or not obj.pk:
            return "Save first"

        url = self._build_full_url(request, obj)
        input_id = f"short-url-{obj.pk}"

        return format_html(
            """
            <div class="short-url-widget" style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                <input
                    id="{}"
                    type="text"
                    value="{}"
                    readonly
                    aria-label="Short URL for {}"
                    style="width: 360px; max-width: 100%;"
                >
                <button
                    type="button"
                    class="short-url-copy"
                >
                    Copy
                </button>
                <span class="short-url-copy-status" role="status"></span>
            </div>
            """,
            input_id,
            url,
            obj.short_code,
        )

    short_url_widget.short_description = "Short URL"

    def qr_code_preview(self, request, obj):
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
            self._build_full_url(request, obj),
            self.QR_PREVIEW_SIZE_PX,
        )

    qr_code_preview.short_description = "QR code"

    def qr_code_image_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            return HttpResponse(status=404)

        if not self.has_view_or_change_permission(request, obj):
            raise PermissionDenied

        img = self._build_qr_image(request, obj)
        buffer = BytesIO()
        img.save(buffer, format=self.QR_DOWNLOAD_FORMAT)
        content = buffer.getvalue()

        response = HttpResponse(content, content_type="image/png")
        response["Content-Disposition"] = f'inline; filename="{self._qr_download_filename(obj)}"'
        return response
