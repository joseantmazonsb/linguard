using Bogus;
using Core.Test.Mocks;
using FluentValidation;
using Linguard.Core.Configuration;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Models.Wireguard.Validators;
using Linguard.Core.OS;
using Linguard.Core.Services;
using Linguard.Core.Utils;
using Linguard.Log;
using Linguard.Web.Auth;
using Linguard.Web.Helpers;
using Linguard.Web.Configuration;
using Linguard.Web.Services;
using Microsoft.AspNetCore.Components.Authorization;
using Microsoft.AspNetCore.Components.Server;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using QRCoder;
using Radzen;
using WebMock;

var root = Path.Combine(new DirectoryInfo(Directory.GetCurrentDirectory()).Parent!.FullName, "Web",
    "wwwroot");
var builder = WebApplication.CreateBuilder(new WebApplicationOptions {
    WebRootPath = root,
    Args = args,
    ApplicationName = AssemblyInfo.Product
});

// Add services to the container.
builder.Services.AddRazorPages();
builder.Services.AddServerSideBlazor();

#region Core services

var manager = new Web.Test.Mocks.DefaultConfigurationManager().Object;
var systemMock = new SystemMock().Object;
var faker = new Faker();
var wireguardServiceMock = new WireguardServiceMock(manager, systemMock, faker).Object;
builder.Services.AddSingleton(manager);
builder.Services.AddSingleton(systemMock);
builder.Services.AddSingleton(wireguardServiceMock);

builder.Services.AddSingleton<Linguard.Core.Managers.IConfigurationManager>(provider 
    => provider.GetRequiredService<IConfigurationManager>());

builder.Services.AddTransient<IWorkingDirectory, WorkingDirectory>();
builder.Services.AddSingleton(DefaultYamlConfigurationSerializer.Instance);
builder.Services.AddTransient<ISystemWrapper, SystemWrapper>();
builder.Services.AddTransient<IWireguardService, WireguardService>();
builder.Services.AddTransient<IInterfaceGenerator, DefaultInterfaceGenerator>();
builder.Services.AddTransient<IClientGenerator, DefaultClientGenerator>();
builder.Services.AddTransient<AbstractValidator<Interface>, InterfaceValidator>();
builder.Services.AddTransient<AbstractValidator<Client>, ClientValidator>();

builder.Services.AddTransient<IInterfaceGenerator, DefaultInterfaceGenerator>();
builder.Services.AddTransient<IClientGenerator, DefaultClientGenerator>();
builder.Services.AddTransient<AbstractValidator<Interface>, InterfaceValidator>();
builder.Services.AddTransient<AbstractValidator<Client>, ClientValidator>();

#endregion

#region Web services

builder.Services.AddSingleton<IWebService, WebService>();
builder.Services.AddSingleton<IStateHasChangedNotifierService, StateHasChangedNotifierService>();
builder.Services.AddTransient<IWebHelper, WebHelper>();
builder.Services.AddTransient<QRCodeGenerator, QRCodeGenerator>();
builder.Services.AddScoped<IAuthenticationService, AuthenticationService>();
builder.Services.AddTransient<ILifetimeService, LifetimeService>();

#region Radzen

builder.Services.AddScoped<DialogService>();
builder.Services.AddScoped<NotificationService>();
builder.Services.AddScoped<TooltipService>();
builder.Services.AddScoped<ContextMenuService>();

#endregion

#endregion

#region Authentication

builder.Services.AddDbContext<ApplicationDbContextMock>();
builder.Services.AddTransient<IdentityDbContext, ApplicationDbContextMock>();
builder.Services.AddDatabaseDeveloperPageExceptionFilter();
builder.Services.AddIdentityCore<IdentityUser>(options => {
        options.SignIn.RequireConfirmedAccount = false;
        options.Password.RequireDigit = false;
        options.Password.RequiredLength = 1;
        options.Password.RequireUppercase = false;
        options.Password.RequireNonAlphanumeric = false;
    })
    .AddRoles<IdentityRole>()
    .AddEntityFrameworkStores<ApplicationDbContextMock>()
    .AddSignInManager();

builder.Services.AddScoped<AuthenticationStateProvider, IdentityAuthenticationStateProvider<IdentityUser>>();
builder.Services.AddScoped<IHostEnvironmentAuthenticationStateProvider>(sp => 
    (ServerAuthenticationStateProvider) sp.GetRequiredService<AuthenticationStateProvider>());

var authCookieFormat = AuthenticationCookieFormat.Default;
builder.Services.AddAuthentication(options => {
    options.DefaultScheme = authCookieFormat.Scheme;
}).AddCookie(authCookieFormat.Scheme, options => {
    options.Cookie.Name = authCookieFormat.Name;
});

#endregion

#region Logging

builder.Logging.AddSimpleFileLogger();

#endregion

var app = builder.Build();

#region Lifetime management

app.Lifetime.ApplicationStarted.Register(() => {
    app.Services.GetService<ILifetimeService>()?.OnAppStarted();
});

app.Lifetime.ApplicationStopping.Register(() => {
    app.Services.GetService<ILifetimeService>()?.OnAppStopping();
});

app.Lifetime.ApplicationStopped.Register(() => {
    app.Services.GetService<ILifetimeService>()?.OnAppStopped();
});
#endregion

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment()) {
    app.UseDeveloperExceptionPage();
}
else {
    app.UseExceptionHandler("/Error");
    // The default HSTS value is 30 days. You may want to change this for production scenarios, see https://aka.ms/aspnetcore-hsts.
    app.UseHsts();
}

app.UseHttpsRedirection();

app.UseStaticFiles();

app.UseRouting();
app.MapBlazorHub();
app.MapFallbackToPage("/_Host");

app.Run();
