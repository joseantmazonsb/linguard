using Core.Test.Mocks;
using FluentValidation;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Models.Wireguard.Validators;
using Linguard.Core.Services;
using Linguard.Core.Utils;
using Linguard.Log;
using Linguard.Web.Services;
using QRCoder;
using Radzen;
using WebMock;
using ILogger = Linguard.Log.ILogger;

var root = Path.Combine(new DirectoryInfo(Directory.GetCurrentDirectory()).Parent!.FullName, "Web",
    "wwwroot");
var builder = WebApplication.CreateBuilder(new WebApplicationOptions {
    WebRootPath = root,
    Args = args,
    ApplicationName = AssemblyInfo.Product
});

//var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddRazorPages();
builder.Services.AddServerSideBlazor();

var manager = new DefaultConfigurationManager().Object;
builder.Services.AddSingleton(manager);
builder.Services.AddTransient<ILogger, NLogLogger>();
var commandRunner = new CommandRunnerMock().Object;
builder.Services.AddSingleton(commandRunner);
builder.Services.AddSingleton(new InterfaceServiceMock(manager).Object);
builder.Services.AddTransient<IWireguardService, WireguardService>();
builder.Services.AddTransient<IInterfaceGenerator, DefaultInterfaceGenerator>();
builder.Services.AddTransient<IClientGenerator, DefaultClientGenerator>();
builder.Services.AddTransient<AbstractValidator<Interface>, InterfaceValidator>();
builder.Services.AddTransient<AbstractValidator<Client>, ClientValidator>();

builder.Services.AddTransient<IWebService, WebService>();
builder.Services.AddTransient<QRCodeGenerator, QRCodeGenerator>();
builder.Services.AddSingleton(new LifetimeServiceMock(manager).Object);

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
