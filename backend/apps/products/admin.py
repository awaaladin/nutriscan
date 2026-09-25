from django.contrib import admin

from .models import CachedExplanation, Product, ProductSubmission

admin.site.register(Product)
admin.site.register(ProductSubmission)
admin.site.register(CachedExplanation)
