// WVP告警弹窗 + 扫描按钮
(function(){
  var lastId = 0;
  var container = document.createElement('div');
  container.id = 'aiw-toast-container';
  container.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:99999;display:flex;flex-direction:column-reverse;gap:10px;max-height:80vh;overflow-y:auto';
  document.body.appendChild(container);

  // 扫描按钮
  var scanBtn = document.createElement('div');
  scanBtn.innerHTML = '📡';
  scanBtn.title = '\u626b\u63cf\u6444\u50cf\u5934';
  scanBtn.style.cssText = 'position:fixed;left:20px;bottom:20px;z-index:99998;width:44px;height:44px;background:#409EFF;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px;cursor:pointer;box-shadow:0 2px 12px rgba(64,158,255,.4)';
  scanBtn.onclick = function(){window.open('http://121.29.248.85:16533/scan','_blank')};
  document.body.appendChild(scanBtn);

  var style = document.createElement('style');
  style.textContent = '.aiw-toast{background:#fff;border-left:4px solid #f56c6c;border-radius:10px;padding:16px 20px;box-shadow:0 6px 30px rgba(0,0,0,.18);max-width:400px;min-width:300px;animation:aiw-slide 0.3s ease;font-size:14px;line-height:1.6;color:#333;cursor:pointer;transition:all 0.3s;position:relative}.aiw-toast:hover{transform:translateY(-2px)}.aiw-toast-title{font-weight:700;color:#f56c6c;margin-bottom:6px;font-size:14px;display:flex;align-items:center;gap:8px}.aiw-toast-title .dot{width:8px;height:8px;background:#f56c6c;border-radius:50%;animation:blink 1s infinite}.aiw-toast-close{position:absolute;top:8px;right:12px;font-size:18px;color:#ccc;cursor:pointer;line-height:1}.aiw-toast-close:hover{color:#f56c6c}.aiw-toast-time{font-size:11px;color:#aaa;margin-top:6px}@keyframes aiw-slide{from{transform:translateX(120%);opacity:0}to{transform:translateX(0);opacity:1}}@keyframes blink{0%,100%{opacity:1}50%{opacity:0}}';
  document.head.appendChild(style);

  function checkAlarms(){
    fetch('http://121.29.248.85:16533/api/alarms?page=1&count=5')
      .then(function(r){return r.json()})
      .then(function(d){
        var list = d.data.list;
        if(list.length > 0){
          var newest = list[0].id;
          if(lastId === 0){
            lastId = newest;
            for(var i = list.length-1; i >= 0; i--){ showToast(list[i]); }
          } else if(newest > lastId){
            for(var i = list.length-1; i >= 0; i--){
              if(list[i].id > lastId){ showToast(list[i]); }
            }
            lastId = newest;
          }
        }
      })
      .catch(function(){});
  }

  function showToast(alarm){
    var toast = document.createElement('div');
    toast.className = 'aiw-toast';
    toast.innerHTML = '<div class="aiw-toast-title"><span class="dot"></span>\u26a0\ufe0f AI\u544a\u8b66<span class="aiw-toast-close">\u00d7</span></div><div>' + (alarm.alarm_description || '') + '</div><div class="aiw-toast-time">' + (alarm.alarm_time || '') + '</div>';
    toast.onclick = function(){this.remove()};
    toast.querySelector('.aiw-toast-close').onclick = function(e){e.stopPropagation();toast.remove()};
    container.appendChild(toast);
  }

  checkAlarms();
  setInterval(checkAlarms, 3000);
})();
