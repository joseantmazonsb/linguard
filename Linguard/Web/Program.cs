using FluentValidation;
using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Models.Wireguard.Validators;
using Linguard.Core.OS;
using Linguard.Core.Services;
using Linguard.Log;
using Linguard.Web.Auth;
using Linguard.Web.Helpers;
using Linguard.Web.Services;
using Microsoft.AspNetCore.Components.Authorization;
using Microsoft.AspNetCore.Components.Server;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore;
using QRCoder;
using Radzen;
using IConfiguration = Linguard.Core.Configuration.IConfiguration;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddRazorPages();
builder.Services.AddServerSideBlazor();

#region Core services

builder.Services.AddSingleton<IConfigurationManager, YamlConfigurationManager>();
builder.Services.AddTransient<IConfiguration, Configuration>();
builder.Services.AddTransient<IWorkingDirectory, WorkingDirectory>();
builder.Services.AddSingleton<IConfigurationSerializer>(DefaultYamlConfigurationSerializer.Instance);
builder.Services.AddTransient<ISystemWrapper, SystemWrapper>();
builder.Services.AddTransient<IWireguardService, WireguardService>();
builder.Services.AddTransient<IInterfaceGenerator, DefaultInterfaceGenerator>();
builder.Services.AddTransient<IClientGenerator, DefaultClientGenerator>();
builder.Services.AddTransient<AbstractValidator<Interface>, InterfaceValidator>();
builder.Services.AddTransient<AbstractValidator<Client>, ClientValidator>();
#endregion

#region Web services

builder.Services.AddSingleton<IWebService, WebService>();
builder.Services.AddTransient<IWebHelper, WebHelper>();
builder.Services.AddTransient<QRCodeGenerator, QRCodeGenerator>();
builder.Services.AddTransient<ILifetimeService, LifetimeService>();
builder.Services.AddTransient<IdentityDbContext, ApplicationDbContext>();
builder.Services.AddScoped<IAuthenticationService, AuthenticationService>();

#region Radzen

builder.Services.AddScoped<DialogService>();
builder.Services.AddScoped<NotificationService>();
builder.Services.AddScoped<TooltipService>();
builder.Services.AddScoped<ContextMenuService>();

#endregion

#endregion

#region Authentication

// var connectionString = builder.Configuration.GetConnectionString("DefaultConnection");
const string connectionString = "DataSource=app.db;Cache=Shared";
builder.Services.AddDbContext<ApplicationDbContext>(options =>
    options.UseSqlite(connectionString));
builder.Services.AddDatabaseDeveloperPageExceptionFilter();
builder.Services.AddIdentityCore<IdentityUser>(options => {
        options.SignIn.RequireConfirmedAccount = false;
        options.Password.RequireDigit = false;
        options.Password.RequiredLength = 1;
        options.Password.RequireUppercase = false;
        options.Password.RequireNonAlphanumeric = false;
    })
    .AddRoles<IdentityRole>()
    .AddEntityFrameworkStores<ApplicationDbContext>()
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
    app.Services.GetService<ILinguardLogger>()!.LogLevel = LogLevel.Debug;
    var scopeFactory = app.Services.GetService<IServiceScopeFactory>();
    var scope = scopeFactory?.CreateScope();
    var context = scope?.ServiceProvider.GetService<ApplicationDbContext>();
    var manager = scope?.ServiceProvider.GetService<UserManager<IdentityUser>>();
    context?.Database.EnsureCreated();
    manager?.CreateAsync(new IdentityUser("test"), "test");
}
else {
    app.UseExceptionHandler("/Error");
    // The default HSTS value is 30 days. You may want to change this for production scenarios, see https://aka.ms/aspnetcore-hsts.
    app.UseHsts();
}

app.UseHttpsRedirection();

app.UseStaticFiles();

app.UseRouting();
app.UseAuthentication();
app.UseAuthorization();
app.MapBlazorHub();
app.MapFallbackToPage("/_Host");

app.Run();
