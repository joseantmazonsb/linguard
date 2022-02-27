using FluentValidation;
using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Models.Wireguard.Validators;
using Linguard.Core.OS;
using Linguard.Core.Services;
using Linguard.Log;
using Linguard.Web.Services;
using QRCoder;
using Radzen;
using IConfiguration = Linguard.Core.Configuration.IConfiguration;
using ILogger = Linguard.Log.ILogger;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddRazorPages();
builder.Services.AddServerSideBlazor();

builder.Services.AddSingleton<IConfigurationManager, YamlConfigurationManager>();
builder.Services.AddTransient<IConfiguration, Configuration>();
builder.Services.AddTransient<IWorkingDirectory, WorkingDirectory>();
builder.Services.AddSingleton<IConfigurationSerializer>(DefaultYamlConfigurationSerializer.Instance);
builder.Services.AddTransient<ILogger, NLogLogger>();
builder.Services.AddTransient<ICommandRunner, CommandRunner>();
builder.Services.AddTransient<IWireguardService, WireguardService>();
builder.Services.AddTransient<IInterfaceService, InterfaceService>();
builder.Services.AddTransient<IInterfaceGenerator, DefaultInterfaceGenerator>();
builder.Services.AddTransient<IClientGenerator, DefaultClientGenerator>();
builder.Services.AddTransient<AbstractValidator<Interface>, InterfaceValidator>();
builder.Services.AddTransient<AbstractValidator<Client>, ClientValidator>();

builder.Services.AddTransient<IWebService, WebService>();
builder.Services.AddTransient<QRCodeGenerator, QRCodeGenerator>();
builder.Services.AddTransient<ILifetimeService, LifetimeService>();

builder.Services.AddScoped<DialogService>();
builder.Services.AddScoped<NotificationService>();
builder.Services.AddScoped<TooltipService>();
builder.Services.AddScoped<ContextMenuService>();

var app = builder.Build();

app.Lifetime.ApplicationStarted.Register(() => {
    app.Services.GetService<ILifetimeService>()?.OnAppStarted();
});

app.Lifetime.ApplicationStopping.Register(() => {
    app.Services.GetService<ILifetimeService>()?.OnAppStopping();
});

app.Lifetime.ApplicationStopped.Register(() => {
    app.Services.GetService<ILifetimeService>()?.OnAppStopped();
});

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
