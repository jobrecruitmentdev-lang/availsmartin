from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate
from .models import User, Address


class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter secure password (min 6 characters)',
            'class': 'w-full px-4 py-3 bg-white border border-emerald-border rounded-full text-textMain placeholder-textMuted/60 focus:outline-none focus:ring-2 focus:ring-emerald focus:border-transparent text-sm transition',
            'autocomplete': 'new-password'
        }),
        min_length=6,
        help_text="At least 6 characters"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm your password',
            'class': 'w-full px-4 py-3 bg-white border border-emerald-border rounded-full text-textMain placeholder-textMuted/60 focus:outline-none focus:ring-2 focus:ring-emerald focus:border-transparent text-sm transition',
            'autocomplete': 'new-password'
        })
    )
    terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must agree to the Terms of Service and Privacy Policy.'}
    )

    class Meta:
        model = User
        fields = ['name', 'email', 'phone']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Your Full Name (e.g. John Doe)',
                'class': 'w-full px-4 py-3 bg-white border border-emerald-border rounded-full text-textMain placeholder-textMuted/60 focus:outline-none focus:ring-2 focus:ring-emerald focus:border-transparent text-sm transition',
                'autocomplete': 'name'
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'name@example.com',
                'class': 'w-full px-4 py-3 bg-white border border-emerald-border rounded-full text-textMain placeholder-textMuted/60 focus:outline-none focus:ring-2 focus:ring-emerald focus:border-transparent text-sm transition',
                'autocomplete': 'email'
            }),
            'phone': forms.TextInput(attrs={
                'placeholder': '+91 9876543210 (Optional)',
                'class': 'w-full px-4 py-3 bg-white border border-emerald-border rounded-full text-textMain placeholder-textMuted/60 focus:outline-none focus:ring-2 focus:ring-emerald focus:border-transparent text-sm transition',
                'autocomplete': 'tel'
            }),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email=email, is_active=True).exists():
            raise ValidationError("An account with this email address already exists. Please sign in.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match. Please re-enter.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class UserLoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'name@example.com',
            'class': 'w-full px-4 py-3 bg-white border border-emerald-border rounded-full text-textMain placeholder-textMuted/60 focus:outline-none focus:ring-2 focus:ring-emerald focus:border-transparent text-sm transition',
            'autocomplete': 'email'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter your password',
            'class': 'w-full px-4 py-3 bg-white border border-emerald-border rounded-full text-textMain placeholder-textMuted/60 focus:outline-none focus:ring-2 focus:ring-emerald focus:border-transparent text-sm transition',
            'autocomplete': 'current-password'
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-emerald rounded border-emerald-border focus:ring-emerald focus:ring-offset-0'
        })
    )


class AdminLoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'admin@availsmart.com',
            'class': 'w-full px-4 py-3 bg-white/90 border border-emerald-dark/30 rounded-full text-textMain placeholder-textMuted/60 focus:outline-none focus:ring-2 focus:ring-emerald focus:border-transparent text-sm transition',
            'autocomplete': 'email'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter admin password',
            'class': 'w-full px-4 py-3 bg-white/90 border border-emerald-dark/30 rounded-full text-textMain placeholder-textMuted/60 focus:outline-none focus:ring-2 focus:ring-emerald focus:border-transparent text-sm transition',
            'autocomplete': 'current-password'
        })
    )


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your registered email address',
            'class': 'w-full px-4 py-3 bg-white border border-emerald-border rounded-full text-textMain placeholder-textMuted/60 focus:outline-none focus:ring-2 focus:ring-emerald focus:border-transparent text-sm transition',
            'autocomplete': 'email'
        })
    )


class ResetPasswordForm(forms.Form):
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter new password (min 6 characters)',
            'class': 'w-full px-4 py-3 bg-white border border-emerald-border rounded-full text-textMain placeholder-textMuted/60 focus:outline-none focus:ring-2 focus:ring-emerald focus:border-transparent text-sm transition',
            'autocomplete': 'new-password'
        }),
        min_length=6
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm new password',
            'class': 'w-full px-4 py-3 bg-white border border-emerald-border rounded-full text-textMain placeholder-textMuted/60 focus:outline-none focus:ring-2 focus:ring-emerald focus:border-transparent text-sm transition',
            'autocomplete': 'new-password'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('new_password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['name', 'phone']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-white border border-emerald-border rounded-full text-textMain text-sm focus:outline-none focus:ring-2 focus:ring-emerald transition',
                'placeholder': 'Your Full Name'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-white border border-emerald-border rounded-full text-textMain text-sm focus:outline-none focus:ring-2 focus:ring-emerald transition',
                'placeholder': '+91 9876543210'
            }),
        }


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            'full_name', 'phone', 'address_line1', 'address_line2',
            'city', 'state', 'pincode', 'country', 'address_type', 'is_default'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-white border border-emerald-border rounded-full text-textMain text-xs font-medium focus:ring-2 focus:ring-emerald focus:outline-none',
                'placeholder': 'Full Name'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-white border border-emerald-border rounded-full text-textMain text-xs font-medium focus:ring-2 focus:ring-emerald focus:outline-none',
                'placeholder': '10-digit mobile number'
            }),
            'address_line1': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-white border border-emerald-border rounded-full text-textMain text-xs font-medium focus:ring-2 focus:ring-emerald focus:outline-none',
                'placeholder': 'Flat, House no., Building, Street'
            }),
            'address_line2': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-white border border-emerald-border rounded-full text-textMain text-xs font-medium focus:ring-2 focus:ring-emerald focus:outline-none',
                'placeholder': 'Landmark, Area (Optional)'
            }),
            'city': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-white border border-emerald-border rounded-full text-textMain text-xs font-medium focus:ring-2 focus:ring-emerald focus:outline-none',
                'placeholder': 'City'
            }),
            'state': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-white border border-emerald-border rounded-full text-textMain text-xs font-medium focus:ring-2 focus:ring-emerald focus:outline-none',
                'placeholder': 'State'
            }),
            'pincode': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-white border border-emerald-border rounded-full text-textMain text-xs font-medium focus:ring-2 focus:ring-emerald focus:outline-none',
                'placeholder': 'Pincode (e.g. 560001)'
            }),
            'country': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-white border border-emerald-border rounded-full text-textMain text-xs font-medium focus:ring-2 focus:ring-emerald focus:outline-none',
                'placeholder': 'Country'
            }),
            'address_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 bg-white border border-emerald-border rounded-full text-textMain text-xs font-semibold focus:ring-2 focus:ring-emerald focus:outline-none'
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-emerald rounded border-emerald-border focus:ring-emerald focus:ring-offset-0'
            }),
        }
