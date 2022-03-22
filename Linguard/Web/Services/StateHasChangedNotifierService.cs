namespace Linguard.Web.Services; 

public class StateHasChangedNotifierService : IStateHasChangedNotifierService {
    private readonly ISet<EventHandler> _handlers = new HashSet<EventHandler>();
    public void Subscribe(EventHandler handler) {
        _handlers.Add(handler);
    }

    public void UnSubscribe(EventHandler handler) {
        _handlers.Remove(handler);
    }

    public void Notify() {
        foreach (var handler in _handlers) {
            handler.Invoke(this, EventArgs.Empty);
        }
    }
}