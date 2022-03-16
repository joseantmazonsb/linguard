async function downloadFileFromStream(fileName, contentStreamReference) {
    const arrayBuffer = await contentStreamReference.arrayBuffer();
    const blob = new Blob([arrayBuffer]);
    const url = URL.createObjectURL(blob);
    triggerFileDownload(fileName, url);
    URL.revokeObjectURL(url);
}

function triggerFileDownload(fileName, url) {
    const anchorElement = document.createElement('a');
    anchorElement.href = url;
    anchorElement.download = fileName ?? '';
    anchorElement.click();
    anchorElement.remove();
}

function setStylesheet(path) {
    const styleSheet = document.getElementById("linguard_style")
    styleSheet.href = path; 
}

window.authFunctions = {
    setCookie: function (name, value, lifetimeInSeconds) {
        const maxAge = `MaxAge=${lifetimeInSeconds}`;
        const nameValue = `${name}=${value}`;
        const path = "Path=/"
        const secure = "Secure"
        const sameSite = "SameSite=None";
        document.cookie = `${nameValue}; ${maxAge}; ${path}; ${secure}; ${sameSite};`;
    },
    deleteCookie: function (name) {
        document.cookie = name + "=; MaxAge=0;";
    }
}

