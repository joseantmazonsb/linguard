document.getElementById('web_secret_key').setAttribute('type', "password");

document.getElementById("toggleSecretKey").addEventListener("click", function () {
    const icon = document.getElementById('toggleSecretKeyIcon')
    const field = document.getElementById('web_secret_key');
    const type = field.getAttribute('type') === 'password' ? 'text' : 'password';
    field.setAttribute('type', type);
    if (type === "password") {
        icon.classList.add('fa-eye-slash');
        icon.classList.remove('fa-eye');
    }
    else {
        icon.classList.add('fa-eye');
        icon.classList.remove('fa-eye-slash');
    }
}, false);

