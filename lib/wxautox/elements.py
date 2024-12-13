from . import uiautomation as uia
from .languages import *
from .utils import *
from .color import *
from .errors import *
import datetime
import time
import os
import re



class WxParam:
    SYS_TEXT_HEIGHT = 33
    TIME_TEXT_HEIGHT = 34
    RECALL_TEXT_HEIGHT = 45
    CHAT_TEXT_HEIGHT = 52
    CHAT_IMG_HEIGHT = 117
    DEFALUT_SAVEPATH = os.path.join(os.getcwd(), 'wxauto文件')
    SHORTCUT_SEND = '{Enter}'
    SAVE_PATH_METHOD = 1   # 1: win32api, 2: uiautomation
    MOUSE_MOVE = False

class WeChatBase:
    def _lang(self, text, langtype='MAIN'):
        if langtype == 'MAIN':
            return MAIN_LANGUAGE[text][self.language]
        elif langtype == 'WARNING':
            return WARNING[text][self.language]

    def _split(self, MsgItem):
        uia.SetGlobalSearchTimeout(0)
        MsgItemName = MsgItem.Name
        if MsgItem.BoundingRectangle.height() == WxParam.SYS_TEXT_HEIGHT:
            Msg = ['SYS', MsgItemName, ''.join([str(i) for i in MsgItem.GetRuntimeId()])]
        elif MsgItem.BoundingRectangle.height() == WxParam.TIME_TEXT_HEIGHT:
            Msg = ['Time', MsgItemName, ''.join([str(i) for i in MsgItem.GetRuntimeId()])]
        elif MsgItem.BoundingRectangle.height() == WxParam.RECALL_TEXT_HEIGHT:
            if '撤回' in MsgItemName:
                Msg = ['Recall', MsgItemName, ''.join([str(i) for i in MsgItem.GetRuntimeId()])]
            else:
                Msg = ['SYS', MsgItemName, ''.join([str(i) for i in MsgItem.GetRuntimeId()])]
        else:
            Index = 1
            User = MsgItem.ButtonControl(foundIndex=Index)
            try:
                while True:
                    if User.Name == '':
                        Index += 1
                        User = MsgItem.ButtonControl(foundIndex=Index)
                    else:
                        break
                winrect = MsgItem.BoundingRectangle
                mid = (winrect.left + winrect.right)/2
                if User.BoundingRectangle.left < mid:
                    if MsgItem.TextControl().Exists(0.1) and MsgItem.TextControl().BoundingRectangle.top < User.BoundingRectangle.top:
                        name = (User.Name, MsgItem.TextControl().Name)
                    else:
                        name = (User.Name, User.Name)
                else:
                    name = 'Self'
                Msg = [name, MsgItemName, ''.join([str(i) for i in MsgItem.GetRuntimeId()])]
            except:
                Msg = ['SYS', MsgItemName, ''.join([str(i) for i in MsgItem.GetRuntimeId()])]
        uia.SetGlobalSearchTimeout(10.0)
        return ParseMessage(Msg, MsgItem, self)
    
    def _getmsgs(self, msgitems, savepic=False, savefile=False, savevoice=False, parseurl=False):
        msgs = []
        for MsgItem in msgitems:
            if MsgItem.ControlTypeName == 'ListItemControl':
                msgs.append(self._split(MsgItem))

        msgtypes = [
            f"[{self._lang('图片')}]",
            f"[{self._lang('文件')}]",
            f"[{self._lang('语音')}]",
            f"[{self._lang('链接')}]",
            f"[{self._lang('音乐')}]",
        ]

        if not [i for i in msgs if i.content[:4] in msgtypes]:
            return msgs

        for msg in msgs:
            if msg.type not in ('friend', 'self'):
                continue
            if msg.content.startswith(f"[{self._lang('图片')}]") and savepic:
                imgpath = self._download_pic(msg.control)
                msg.content = imgpath if imgpath else msg.content
            elif msg.content.startswith(f"[{self._lang('文件')}]") and savefile:
                filepath = self._download_file(msg.control)
                msg.content = filepath if filepath else msg.content
            elif msg.content.startswith(f"[{self._lang('语音')}]") and savevoice:
                voice_text = self._get_voice_text(msg.control)
                msg.content = voice_text if voice_text else msg.content
            elif msg.content in (f"[{self._lang('链接')}]", f"[{self._lang('音乐')}]") and parseurl:
                card_url = self._get_card_url(msg.control, msg.content)
                msg.content = f"[wxauto卡片链接解析]{card_url}" if card_url else msg.content
            msg.info[1] = msg.content
        return msgs
    
    def _download_pic(self, msgitem):
        
        imgcontrol = msgitem.ButtonControl(Name='')
        if not imgcontrol.Exists(0.5):
            return None
        RollIntoView(self.C_MsgList, imgcontrol)
        imgcontrol.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        imgobj = WeChatImage()
        savepath = imgobj.Save()
        imgobj.Close()
        return savepath

    def _download_file(self, msgitem):
        filecontrol = msgitem.ButtonControl(Name='')
        if not filecontrol.Exists(0.5):
            return None
        RollIntoView(self.C_MsgList, filecontrol)
        filecontrol.RightClick(simulateMove=False)
        # filename = msgitem.GetProgenyControl(9, control_type='TextControl').Name
        filesize = msgitem.GetProgenyControl(10, control_type='TextControl').Name
        menu = self.UiaAPI.MenuControl(ClassName='CMenuWnd')
        while not menu.Exists(0.1):
            filecontrol.RightClick(simulateMove=False)
        copy_option = menu.ListControl().MenuItemControl(Name='复制')
        if copy_option.Exists(0.5):
            while True:
                try:
                    copy_option.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                    filepath = ReadClipboardData().get('15')[0]
                    break
                except Exception as e:
                    while not menu.Exists(0.1):
                        filecontrol.RightClick(simulateMove=False)
                    copy_option = menu.ListControl().MenuItemControl(Name='复制')
        else:
            filecontrol.RightClick(simulateMove=False)
            if filesize >= '200M':
                print('文件过大，点击接收文件')
                filecontrol.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                filewin = self.UiaAPI.WindowControl(ClassName='MsgFileWnd')
                accept_button = filewin.ButtonControl(Name='接收文件')
                if accept_button.Exists(2):
                    accept_button.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            
            while True:
                try:
                    if msgitem.TextControl(Name='接收中').Exists(0):
                        time.sleep(1)
                        continue
                    filecontrol = msgitem.ButtonControl(Name='')
                    menu = self.UiaAPI.MenuControl(ClassName='CMenuWnd')
                    while not menu.Exists(0.1):
                        filecontrol.RightClick(simulateMove=False)
                    copy_option = menu.ListControl().MenuItemControl(Name='复制')
                    if copy_option.Exists(0.5):
                        copy_option.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                        filepath = ReadClipboardData().get('15')[0]
                        break
                    else:
                        filecontrol.RightClick(simulateMove=False)
                except Exception as e:
                    pass
                time.sleep(1)
        
        savepath = os.path.join(WxParam.DEFALUT_SAVEPATH, os.path.split(filepath)[1])
        if not os.path.exists(WxParam.DEFALUT_SAVEPATH):
            os.makedirs(WxParam.DEFALUT_SAVEPATH)
        t0 = time.time()
        while time.time() - t0 < 10:
            try:
                shutil.copyfile(filepath, savepath)
                return savepath
            except FileNotFoundError:
                time.sleep(0.1)
                continue
        

    def _get_voice_text(self, msgitem):
        if msgitem.GetProgenyControl(8, 4):
            return msgitem.GetProgenyControl(8, 4).Name
        voicecontrol = msgitem.ButtonControl(Name='')
        if not voicecontrol.Exists(0.5):
            return None
        RollIntoView(self.C_MsgList, voicecontrol)
        msgitem.GetProgenyControl(7, 1).RightClick(simulateMove=False)
        menu = self.UiaAPI.MenuControl(ClassName='CMenuWnd')
        option = menu.MenuItemControl(Name="语音转文字")
        if not option.Exists(0.5):
            voicecontrol.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            if not msgitem.GetProgenyControl(8, 4):
                return None
        else:
            option.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)

        text = ''
        while True:
            if msgitem.GetProgenyControl(8, 4):
                if msgitem.GetProgenyControl(8, 4).Name == text:
                    return text
                text = msgitem.GetProgenyControl(8, 4).Name
            time.sleep(0.1)

    def _get_card_url(self, msgitem, content):
        if content not in ('[链接]', '[音乐]'):
            return None
        if content == '[链接]' and (
            msgitem.TextControl(Name="邀请你加入群聊").Exists(0)\
            or msgitem.TextControl(Name="Group Chat Invitation").Exists(0)):
            return '[链接](群聊邀请)'
        if not msgitem.PaneControl().Exists(0):
            return None
        link_control_list = msgitem.PaneControl().GetChildren()
        if len(link_control_list) < 2:
            return None
        link_control = link_control_list[1]
        if not link_control.ButtonControl().Exists(0):
            return None

        RollIntoView(self.C_MsgList, link_control)
        # msgitem.TextControl().Click()
        msgitem.GetAllProgeny()[-1][-1].Click()
        t0 = time.time()
        while not FindWindow('Chrome_WidgetWin_0', '微信'):
            if time.time() - t0 > 10:
                raise TimeoutError('Open url timeout')
            time.sleep(0.01)
        wxbrowser = uia.PaneControl(ClassName="Chrome_WidgetWin_0", Name="微信", searchDepth=1)

        while not wxbrowser.DocumentControl().GetChildren() or wxbrowser.DocumentControl().TextControl(Name="mp appmsg sec open").Exists(0):
            if time.time() - t0 > 10:
                raise TimeoutError('Open url timeout')
            time.sleep(0.01)
        wxbrowser.PaneControl(searchDepth=1, ClassName='').MenuItemControl(Name="更多").Click()
        wxbrowser = uia.PaneControl(ClassName="Chrome_WidgetWin_0", Name="微信", searchDepth=1)
        time.sleep(0.5)
        copyurl = wxbrowser.PaneControl(ClassName='Chrome_WidgetWin_0').MenuItemControl(Name='复制链接')
        if copyurl.Exists(3):
            copyurl.Click()
        else:
            return '[链接]无法获取url'
        url = ReadClipboardData()['13']
        wxbrowser.PaneControl(searchDepth=1, ClassName='').ButtonControl(Name="关闭").Click()
        return url


class ChatWnd(WeChatBase):
    _clsname = 'ChatWnd'

    def __init__(self, who, wx, language='cn'):
        self.who = who
        self._wx = wx
        self.language = language
        self.usedmsgid = []
        self.UiaAPI = uia.WindowControl(searchDepth=1, ClassName=self._clsname, Name=who)
        self.editbox = self.UiaAPI.EditControl()
        self.C_MsgList = self.UiaAPI.ListControl()
        self.GetAllMessage()

        self.savepic = False   # 该参数用于在自动监听的情况下是否自动保存聊天图片

    def __repr__(self) -> str:
        return f"<wxauto Chat Window at {hex(id(self))} for {self.who}>"

    def _show(self):
        self.HWND = FindWindow(name=self.who, classname=self._clsname)
        win32gui.ShowWindow(self.HWND, 1)
        win32gui.SetWindowPos(self.HWND, -1, 0, 0, 0, 0, 3)
        win32gui.SetWindowPos(self.HWND, -2, 0, 0, 0, 0, 3)
        self.UiaAPI.SwitchToThisWindow()

    def Close(self):
        try:
            self.UiaAPI.SendKeys('{Esc}')
        except:
            pass

    def ChatInfo(self):

        chat_info = {}

        chat_name_control = self.UiaAPI.GetProgenyControl(11)
        chat_name_control_list = chat_name_control.GetChildren()
        chat_name_control_count = len(chat_name_control_list)
        if chat_name_control_count == 1:
            if self.UiaAPI.ButtonControl(Name='公众号主页').Exists(0):
                chat_info['chat_type'] = 'official'
            else:
                chat_info['chat_type'] = 'friend'
            chat_info['chat_name'] = chat_name_control_list[0].Name
        elif chat_name_control_count == 2:
            chat_info['chat_type'] = 'group'
            chat_info['chat_name'] = chat_name_control_list[0].Name.replace(chat_name_control_list[-1].Name, '')
            chat_info['group_member_count'] = int(chat_name_control_list[-1].Name.replace('(', '').replace(')', '').replace(' ', ''))
            ori_chat_name_control = chat_name_control_list[0].GetParentControl().GetParentControl().TextControl(searchDepth=1)
            if ori_chat_name_control.Exists(0):
                chat_info['chat_remark'] = chat_info['chat_name']
                chat_info['chat_name'] = ori_chat_name_control.Name
        return chat_info

    def AtAll(self, msg=None):
        """@所有人
        
        Args:
            msg (str, optional): 要发送的文本消息
        """
        wxlog.debug(f"@所有人：{self.who} --> {msg}")
        
        if not self.editbox.HasKeyboardFocus:
            self.editbox.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)

        self.editbox.Input('@')
        atwnd = self.UiaAPI.PaneControl(ClassName='ChatContactMenu')
        if atwnd.Exists(maxSearchSeconds=0.1):
            atwnd.ListItemControl(Name='所有人').Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            if msg:
                if not msg.startswith('\n'):
                    msg = '\n' + msg
                self.SendMsg(msg)
            else:
                self.editbox.SendKeys(WxParam.SHORTCUT_SEND)

    def SendTypingText(self, msg, clear=True):
        """发送文本消息（打字机模式），支持换行及@功能

        Args:
            msg (str): 要发送的文本消息
            who (str): 要发送给谁，如果为None，则发送到当前聊天页面。  *最好完整匹配，优先使用备注
            clear (bool, optional): 是否清除原本的内容，

        Example:
            >>> wx = WeChat()
            >>> wx.SendTypingText('你好', who='张三')

            换行及@功能：
            >>> wx.SendTypingText('各位下午好\n{@张三}负责xxx\n{@李四}负责xxxx', who='工作群')
        """
        if not msg:
            return None
        
        if clear:
            self.editbox.ShortcutSelectAll(move=WxParam.MOUSE_MOVE)

        def _at(name):
            self.editbox.Input(name)
            atwnd = self.UiaAPI.PaneControl(ClassName='ChatContactMenu')
            if atwnd.Exists(maxSearchSeconds=0.1):
                self.UiaAPI.SendKeys('{ENTER}')

        atlist = re.findall(r'{(@.*?)}', msg)
        for name in atlist:
            text, msg = msg.split(f'{{{name}}}')
            self.editbox.Input(text)
            _at(name)
        self.editbox.Input(msg)
        self.UiaAPI.SendKeys(WxParam.SHORTCUT_SEND)

    def SendMsg(self, msg, at=None):
        """发送文本消息

        Args:
            msg (str): 要发送的文本消息
            at (str|list, optional): 要@的人，可以是一个人或多个人，格式为str或list，例如："张三"或["张三", "李四"]
        """
        wxlog.debug(f"发送消息：{self.who} --> {msg}")
        
        if not self.editbox.HasKeyboardFocus:
            self.editbox.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)

        if at:
            if isinstance(at, str):
                at = [at]
            for i in at:
                self.editbox.Input('@'+i)
                atwnd = self.UiaAPI.PaneControl(ClassName='ChatContactMenu')
                if atwnd.Exists(maxSearchSeconds=0.1):
                    atwnd.SendKeys('{ENTER}')
                    if msg and not msg.startswith('\n'):
                        msg = '\n' + msg

        t0 = time.time()
        while True:
            if time.time() - t0 > 10:
                wxlog.debug(ReadClipboardData())
                raise TimeoutError(f'发送消息超时 --> {self.who} - {msg}')
            SetClipboardText(msg)
            if not self.editbox.HasKeyboardFocus:
                self.editbox.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            self.editbox.ShortcutPaste(move=WxParam.MOUSE_MOVE)
            wxlog.debug(ReadClipboardData())
            if self.editbox.GetValuePattern().Value:
                break
        self.editbox.SendKeys(WxParam.SHORTCUT_SEND)

    def SendEmotion(self, emotion_index):
        """发送自定义表情

        Args:
            emotion_index (int): 表情序号，从0开始
        """
        self.UiaAPI.ButtonControl(RegexName='表情.*?').Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        EmotionWnd = self.UiaAPI.PaneControl(ClassName='EmotionWnd')
        my_emotion_icon = EmotionWnd.CheckBoxControl(Name='添加的单个表情')
        while not my_emotion_icon.Exists(0):
            EmotionWnd.CheckBoxControl().GetParentControl().WheelUp(wheelTimes=10)
        my_emotion_icon.Click(move=False, simulateMove=False, return_pos=False)
        emotion_list = EmotionWnd.ListControl()
        while not emotion_list.TextControl(Name="添加的单个表情").Exists(0):
            emotion_list.WheelUp(wheelTimes=10)

        emotions = emotion_list.GetChildren()[1:]
        amount = len(emotions)
        last_one = emotions[-1]
        top0 = emotions[0].BoundingRectangle.top
        for idx, e in enumerate(emotions):
            if e.BoundingRectangle.top != top0:
                break

        def next_page(index, emotion_list, emotions, last_one, idx, amount):
            if index < len(emotions):
                time.sleep(1)
                emotion = emotions[index]
                return emotion
            else:
                while True:
                    position = last_one.BoundingRectangle.top
                    emotions = emotion_list.GetChildren()
                    if last_one.GetRuntimeId() == emotions[idx-1].GetRuntimeId():
                        break
                    emotion_list.WheelDown()
                    time.sleep(0.05)
                    if last_one.BoundingRectangle.top == position:
                        return 
                fourth = emotions[idx*2- 1]
                while True:
                    position = fourth.BoundingRectangle.top
                    emotions = emotion_list.GetChildren()
                    if fourth.GetRuntimeId() == emotions[idx-1].GetRuntimeId():
                        new_index = index - amount
                        last_one = emotions[-1]
                        amount = len(emotions)
                        return next_page(new_index, emotion_list, emotions, last_one, idx, amount)
                    emotion_list.WheelDown()
                    time.sleep(0.05)
                    if fourth.BoundingRectangle.top == position:
                        return
        
        emotion = next_page(emotion_index, emotion_list, emotions, last_one, idx, amount)
        if emotion is not None:
            RollIntoView(emotion_list, emotion)
            emotion.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            return True
        else:
            wxlog.debug(f'未找到表情索引：{emotion_index}')
            EmotionWnd.SendKeys('{Esc}')
            return False

    def SendFiles(self, filepath):
        """向当前聊天窗口发送文件
        
        Args:
            filepath (str|list): 要复制文件的绝对路径  
            
        Returns:
            bool: 是否成功发送文件
        """
        wxlog.debug(f"发送文件：{self.who} --> {filepath}")
        filelist = []
        if isinstance(filepath, str):
            if not os.path.exists(filepath):
                Warnings.lightred(f'未找到文件：{filepath}，无法成功发送', stacklevel=2)
                return False
            else:
                filelist.append(os.path.realpath(filepath))
        elif isinstance(filepath, (list, tuple, set)):
            for i in filepath:
                if os.path.exists(i):
                    filelist.append(i)
                else:
                    Warnings.lightred(f'未找到文件：{i}', stacklevel=2)
        else:
            Warnings.lightred(f'filepath参数格式错误：{type(filepath)}，应为str、list、tuple、set格式', stacklevel=2)
            return False
        
        if filelist:
            
            self.editbox.ShortcutSelectAll(move=WxParam.MOUSE_MOVE)
            t0 = time.time()
            while True:
                if time.time() - t0 > 10:
                    raise TimeoutError(f'发送文件超时 --> {filelist}')
                SetClipboardFiles(filelist)
                time.sleep(0.2)
                self.editbox.ShortcutPaste(move=WxParam.MOUSE_MOVE)
                t1 = time.time()
                while time.time() - t1 < 5:
                    try:
                        edit_value = self.editbox.GetValuePattern().Value
                        break
                    except:
                        time.sleep(0.1)

                if edit_value:
                    break
            
            t0 = time.time()
            while time.time() - t0 < 10:
                t1 = time.time()
                while time.time() - t1 < 5:
                    try:
                        edit_value = self.editbox.GetValuePattern().Value
                        break
                    except:
                        time.sleep(0.1)
                if not edit_value:
                    break
                self.editbox.SendKeys(WxParam.SHORTCUT_SEND)
                time.sleep(0.1)
            return True
        else:
            Warnings.lightred('所有文件都无法成功发送', stacklevel=2)
            return False
        
    def GetAllMessage(self, savepic=False, savefile=False, savevoice=False, parseurl=False):
        '''获取当前窗口中加载的所有聊天记录
        
        Args:
            savepic (bool): 是否自动保存聊天图片
            savefile (bool): 是否自动保存聊天文件
            savevoice (bool): 是否自动保存语音转文字
            parseurl (bool): 是否解析链接
            
        Returns:
            list: 聊天记录信息
        '''
        wxlog.debug(f"获取所有聊天记录：{self.who}")
        MsgItems = self.C_MsgList.GetChildren()
        msgs = self._getmsgs(MsgItems, savepic, savefile, savevoice, parseurl)
        return msgs
    
    def GetNewMessage(self, savepic=False, savefile=False, savevoice=False, parseurl=False):
        '''获取当前窗口中加载的新聊天记录

        Args:
            savepic (bool): 是否自动保存聊天图片
            savefile (bool): 是否自动保存聊天文件
            savevoice (bool): 是否自动保存语音转文字
            parseurl (bool): 是否解析链接
        
        Returns:
            list: 新聊天记录信息
        '''
        wxlog.debug(f"获取新聊天记录：{self.who}")
        if not self.usedmsgid:
            self.usedmsgid = [i[-1] for i in self.GetAllMessage()]
            return []
        MsgItems = self.C_MsgList.GetChildren()
        NewMsgItems = [i for i in MsgItems if ''.join([str(i) for i in i.GetRuntimeId()]) not in self.usedmsgid]
        if not NewMsgItems:
            return []
        nowmsgids = [''.join([str(i) for i in i.GetRuntimeId()]) for i in MsgItems]
        for msgid in self.usedmsgid[::-1]:
            if msgid in nowmsgids:
                idx = nowmsgids.index(msgid)
                lastmsgcontrol = MsgItems[idx]
                top_lastmsg = lastmsgcontrol.BoundingRectangle.top
                NewMsgItems = [i for i in NewMsgItems if i.BoundingRectangle.top > top_lastmsg]
                break
        if not NewMsgItems:
            return []
        
        newmsgs = self._getmsgs(NewMsgItems, savepic, savefile, savevoice, parseurl)
        self.usedmsgid = list(self.usedmsgid + [i[-1] for i in newmsgs])[-100:]
        # if newmsgs[0].type == 'sys' and newmsgs[0].content == self._lang('查看更多消息'):
        #     newmsgs = newmsgs[1:]
        return newmsgs

    
    def LoadMoreMessage(self):
        """加载当前聊天页面更多聊天信息
        
        Returns:
            bool: 是否成功加载更多聊天信息
        """
        wxlog.debug(f"加载更多聊天信息：{self.who}")
        
        loadmore = self.C_MsgList.GetFirstChildControl()
        loadmore_top = loadmore.BoundingRectangle.top
        top = self.C_MsgList.BoundingRectangle.top
        while True:
            if loadmore.BoundingRectangle.top > top or loadmore.Name == '':
                isload = True
                break
            else:
                self.C_MsgList.WheelUp(wheelTimes=10, waitTime=0.1)
                if loadmore.BoundingRectangle.top == loadmore_top:
                    isload = False
                    break
                else:
                    loadmore_top = loadmore.BoundingRectangle.top
        self.C_MsgList.WheelUp(wheelTimes=1, waitTime=0.1)
        return isload

    def GetGroupMembers(self, add_friend_mode=False):
        """获取当前聊天群成员

        Returns:
            list: 当前聊天群成员列表
        """
        wxlog.debug(f"获取当前聊天群成员：{self.who}")
        ele = self.UiaAPI.PaneControl(searchDepth=7, foundIndex=6).ButtonControl(Name='聊天信息')
        try:
            uia.SetGlobalSearchTimeout(1)
            rect = ele.BoundingRectangle
            Click(rect)
        except:
            return 
        finally:
            uia.SetGlobalSearchTimeout(10)
        roominfoWnd = self.UiaAPI.WindowControl(ClassName='SessionChatRoomDetailWnd', searchDepth=1)
        more = roominfoWnd.ButtonControl(Name='查看更多', searchDepth=8)
        if more.Exists(0.1):
            more.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        
        if add_friend_mode:
            members = [GroupMemberElement(i, self) for i in roominfoWnd.ListControl(Name='聊天成员').GetChildren()]
            while members[-1].nickname in ['添加', '移出']:
                members = members[:-1]
            return members
        else:
            members = [i.Name for i in roominfoWnd.ListControl(Name='聊天成员').GetChildren()]
            while members[-1] in ['添加', '移出']:
                members = members[:-1]
            roominfoWnd.SendKeys('{Esc}')
            return members
        
    def ManageGroup(self, name=None, remark=None, myname=None, notice=None, quit=False):
        """管理当前聊天页面的群聊
        
        Args:
            name (str, optional): 修改群名称
            remark (str, optional): 备注名
            myname (str, optional): 我的群昵称
            notice (str, optional): 群公告
            quit (bool, optional): 是否退出群，当该项为True时，其他参数无效
        
        Returns:
            dict: 修改结果
        """
        edit_result = {}
        chat_info = self.ChatInfo()
        if chat_info['chat_type'] != 'group':
            wxlog.debug('当前聊天对象不是群聊')
            return False
        ele = self.UiaAPI.PaneControl(searchDepth=7, foundIndex=6).ButtonControl(Name='聊天信息')
        ele.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=True)
        roomwnd = SessionChatRoomDetailWnd(self)
        if quit:
            quit_result = roomwnd.quit()
            edit_result['quit'] = quit_result
            return edit_result
        if name is not None:
            edit_name_result = roomwnd.edit_group_name(name)
            edit_result['name'] = edit_name_result
        if remark is not None:
            edit_remark_result = roomwnd.edit_remark(remark)
            edit_result['remark'] = edit_remark_result
        if myname is not None:
            edit_myname_result = roomwnd.edit_myname(myname)
            edit_result['myname'] = edit_myname_result
        if notice is not None:
            edit_notice_result = roomwnd.edit_notice(notice)
            edit_result['notice'] = edit_notice_result
        roomwnd.close()
        return edit_result
    
    def CallGroupMsg(self, members):
        """发起群语音通话
        
        Args:
            group (str): 群名或备注名
            members (list): 成员列表，列表元素可以是好友微信号、昵称、备注名
        """
        wxlog.debug(f"发起群语音通话：{members}")
        chat_info = self.ChatInfo()
        if chat_info['chat_type'] != 'group':
            wxlog.debug('当前聊天对象不是群聊')
            return False
        
        self.UiaAPI.ButtonControl(Name='语音聊天').Click()
        addwnd = AddTalkMemberWnd(self)
        if not addwnd.UiaAPI.Exists(5):
            return False
        for member in members:
            addwnd.Add(member)
        addwnd.Submit()

class ChatRecordWnd:
    def __init__(self):
        self.api = uia.WindowControl(ClassName='ChatRecordWnd', searchDepth=1)

    def GetContent(self):
        """获取聊天记录内容"""
        
        msgids = []
        msgs = []
        listcontrol = self.api.ListControl(Name='消息记录')
        while True:
            listitems = listcontrol.GetChildren()
            listitemids = [item.GetRuntimeId() for item in listitems]
            try:
                msgids = msgids[msgids.index(listitemids[0]):]
            except:
                pass
            for item in listitems:
                msgid = item.GetRuntimeId()
                if msgid not in msgids:
                    msgids.append(msgid)
                    sender = item.GetProgenyControl(4, control_type='TextControl').Name
                    msgtime = ParseWeChatTime(item.GetProgenyControl(4, 1, control_type='TextControl').Name)
                    if '[图片]' in item.Name:
                        imgcontrol = item.GetProgenyControl(6, control_type='ButtonControl')
                        # wait for image loading
                        for _ in range(10):
                            if imgcontrol:
                                RollIntoView(listcontrol, imgcontrol, True)
                                imgcontrol.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                                img = WeChatImage()
                                imgpath = img.Save()
                                img.Close()
                                msgs.append([sender, imgpath, msgtime])
                                break
                            else:
                                time.sleep(1)
                    elif item.Name == '' and item.TextControl(Name='视频').Exists(0.3):
                        videocontrol = item.GetProgenyControl(5, control_type='ButtonControl')
                        if videocontrol:
                            RollIntoView(listcontrol, videocontrol, True)
                            videocontrol.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                            video = WeChatImage(video=True)
                            videopath = video.Save()
                            video.Close()
                            msgs.append([sender, videopath, msgtime])
                    else:
                        textcontrols = [i for i in GetAllControl(item) if i.ControlTypeName == 'TextControl']
                        who = textcontrols[0].Name
                        try:
                            content = textcontrols[2].Name
                        except IndexError:
                            content = ''
                        msgs.append([sender, content, msgtime])
            topcontrol = listitems[-1]
            top = topcontrol.BoundingRectangle.top
            self.api.WheelDown(wheelTimes=3)
            time.sleep(0.1)
            if topcontrol.Exists(0.1) and top == topcontrol.BoundingRectangle.top and listitemids == [item.GetRuntimeId() for item in listcontrol.GetChildren()]:
                self.api.SendKeys('{Esc}')
                return msgs

class WeChatImage:
    _clsname = 'ImagePreviewWnd'

    def __init__(self, video=False, language='cn') -> None:
        self._video_mode = video
        self.language = language
        self.api = uia.WindowControl(ClassName=self._clsname, searchDepth=1)
        MainControl1 = [i for i in self.api.GetChildren() if not i.ClassName][0]
        self.ToolsBox, self.PhotoBox = MainControl1.GetChildren()
        
        # tools按钮
        self.t_previous = self.ToolsBox.ButtonControl(Name=self._lang('上一张'))
        self.t_next = self.ToolsBox.ButtonControl(Name=self._lang('下一张'))
        self.t_zoom = self.ToolsBox.ButtonControl(Name=self._lang('放大'))
        self.t_translate = self.ToolsBox.ButtonControl(Name=self._lang('翻译'))
        self.t_ocr = self.ToolsBox.ButtonControl(Name=self._lang('提取文字'))
        self.t_save = self.api.ButtonControl(Name=self._lang('另存为...'))
        self.t_qrcode = self.ToolsBox.ButtonControl(Name=self._lang('识别图中二维码'))

    def __repr__(self) -> str:
        return f"<wxauto WeChat Image at {hex(id(self))}>"
    
    def _lang(self, text):
        return IMAGE_LANGUAGE[text][self.language]
    
    def _show(self):
        HWND = FindWindow(classname=self._clsname)
        win32gui.ShowWindow(HWND, 1)
        self.api.SwitchToThisWindow()
        
    def OCR(self):
        result = ''
        ctrls = self.PhotoBox.GetChildren()
        if len(ctrls) == 2:
            self.t_ocr.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        ctrls = self.PhotoBox.GetChildren()
        if len(ctrls) != 3:
            Warnings.lightred('获取文字识别失败', stacklevel=2)
        else:
            TranslateControl = ctrls[-1]
            result = TranslateControl.TextControl().Name
        return result

    
    def Save(self, savepath='', timeout=10):
        """保存图片/视频

        Args:
            savepath (str): 绝对路径，包括文件名和后缀，例如："D:/Images/微信图片_xxxxxx.jpg"
            （如果不填，则默认为当前脚本文件夹下，新建一个“微信图片(或视频)”的文件夹，保存在该文件夹内）
        
        Returns:
            str: 文件保存路径，即savepath
        """
        if WxParam.MOUSE_MOVE:
            self._show()
        if not savepath:
            if self._video_mode:
                savepath = os.path.join(WxParam.DEFALUT_SAVEPATH, f"微信视频_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}.mp4")
            else:
                savepath = os.path.join(WxParam.DEFALUT_SAVEPATH, f"微信图片_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}.jpg")
        if not os.path.exists(os.path.split(savepath)[0]):
            os.makedirs(os.path.split(savepath)[0])
            
        if self.t_save.Exists(maxSearchSeconds=5):
            time.sleep(0.3)
            self.t_save.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        else:
            raise TimeoutError('下载超时')
        time.sleep(0.5)
        t0 = time.time()
        while True:
            if time.time() - t0 > timeout:
                raise TimeoutError('下载超时')
            handle = FindWindow(name='另存为...')
            if handle:
                break
        t0 = time.time()
        while True:
            if time.time() - t0 > timeout:
                raise TimeoutError('下载超时')
            try:
                edithandle = [i for i in GetAllWindowExs(handle) if i[1] == 'Edit' and i[-1]][0][0]
                savehandle = FindWinEx(handle, classname='Button', name='保存(&S)')[0]
                if edithandle and savehandle:
                    break
            except:
                pass
        time.sleep(0.3)
        if WxParam.SAVE_PATH_METHOD == 1:
            win32gui.SendMessage(edithandle, win32con.WM_SETTEXT, '', str(savepath))
        elif WxParam.SAVE_PATH_METHOD == 2:
            path_control = uia.WindowControl(Name='图片查看',ClassName="ImagePreviewWnd", searchDepth=1).EditControl(Name="文件名:")
            SetClipboardText(savepath)
            path_control.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            path_control.SendKeys('{Ctrl}A', api=False)
            path_control.SendKeys('{Ctrl}V', api=False)
        # time.sleep(0.3)
        win32gui.SendMessage(savehandle, win32con.BM_CLICK, 0, 0)
        return savepath
        
    def Previous(self):
        """上一张"""
        if self.t_previous.IsKeyboardFocusable:
            
            self.t_previous.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            return True
        else:
            Warnings.lightred('上一张按钮不可用', stacklevel=2)
            return False
        
    def Next(self, warning=True):
        """下一张"""
        if self.t_next.IsKeyboardFocusable:
            
            self.t_next.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            return True
        else:
            if warning:
                Warnings.lightred('已经是最新的图片了', stacklevel=2)
            return False
        
    def Close(self):
        self.api.SendKeys('{Esc}')
    
class TextElement:
    def __init__(self, ele, wx) -> None:
        self._wx = wx
        chatname = wx.CurrentChat()
        self.ele = ele
        self.sender = ele.ButtonControl(foundIndex=1, searchDepth=2)
        _ = ele.GetFirstChildControl().GetChildren()[1].GetChildren()
        if len(_) == 1:
            self.content = _[0].TextControl().Name
            self.chattype = 'friend'
            self.chatname = chatname
        else:
            self.sender_remark = _[0].TextControl().Name
            self.content = _[1].TextControl().Name
            self.chattype = 'group'
            numtext = re.findall(' \(\d+\)', chatname)[-1]
            self.chatname = chatname[:-len(numtext)]
            
        self.info = {
            'sender': self.sender.Name,
            'content': self.content,
            'chatname': self.chatname,
            'chattype': self.chattype,
            'sender_remark': self.sender_remark if hasattr(self, 'sender_remark') else ''
        }

    def __repr__(self) -> str:
        return f"<wxauto Text Element at {hex(id(self))} ({self.sender.Name}: {self.content})>"

class NewFriendsElement:
    def __init__(self, ele, wx):
        self._wx = wx
        self.ele = ele
        self.name = self.ele.Name
        self.msg = self.ele.GetFirstChildControl().PaneControl(SearchDepth=1).GetChildren()[-1].TextControl().Name
        self.ele.GetChildren()[-1]
        self.NewFriendsBox = self._wx.ChatBox.ListControl(Name='新的朋友').GetParentControl()
        self.Status = self.ele.GetFirstChildControl().GetChildren()[-1]
        self.acceptable = isinstance(self.Status, uia.ButtonControl)
            
    def __repr__(self) -> str:
        return f"<wxauto New Friends Element at {hex(id(self))} ({self.name}: {self.msg})>"

    def Accept(self, remark=None, tags=None, permission='朋友圈'):
        """接受好友请求
        
        Args:
            remark (str, optional): 备注名
            tags (list, optional): 标签列表
            permission (str, optional): 朋友圈权限, 可选值：'朋友圈', '仅聊天'
        """
        if not self.acceptable:
            wxlog.debug(f"当前好友状态无法接受好友请求：{self.name}")
            return 
        wxlog.debug(f"接受好友请求：{self.name}  备注：{remark} 标签：{tags}")
        self._wx._show()
        RollIntoView(self.NewFriendsBox, self.Status)
        self.Status.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        NewFriendsWnd = self._wx.UiaAPI.WindowControl(ClassName='WeUIDialog')
        tipscontrol = NewFriendsWnd.TextControl(Name="你的联系人较多，添加新的朋友时需选择权限")

        permission_sns = NewFriendsWnd.CheckBoxControl(Name='聊天、朋友圈、微信运动等')
        permission_chat = NewFriendsWnd.CheckBoxControl(Name='仅聊天')
        if tipscontrol.Exists(0.5):
            permission_sns = tipscontrol.GetParentControl().GetParentControl().TextControl(Name='朋友圈')
            permission_chat = tipscontrol.GetParentControl().GetParentControl().TextControl(Name='仅聊天')

        if remark:
            remarkedit = NewFriendsWnd.TextControl(Name='备注名').GetParentControl().EditControl()
            remarkedit.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            remarkedit.ShortcutSelectAll(move=WxParam.MOUSE_MOVE)
            remarkedit.Input(remark)
        
        if tags:
            tagedit = NewFriendsWnd.TextControl(Name='标签').GetParentControl().EditControl()
            for tag in tags:
                tagedit.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                tagedit.Input(tag)
                NewFriendsWnd.PaneControl(ClassName='DropdownWindow').TextControl().Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)

        if permission == '朋友圈':
            permission_sns.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        elif permission == '仅聊天':
            permission_chat.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)

        NewFriendsWnd.ButtonControl(Name='确定').Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)

    def GetAccount(self, wait=5):
        """获取好友号
        
        Args:
            wait (int, optional): 等待时间
            
        Returns:
            str: 好友号，如果获取失败则返回None
        """
        # if isinstance(self.Status, uia.ButtonControl):
        #     wxlog.debug(f"非好友状态无法获取好友号：{self.name}")
        #     return 
        wxlog.debug(f"获取好友号：{self.name}")
        self.ele.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        account_tag_control = self._wx.ChatBox.TextControl(Name='微信号：')
        if account_tag_control.Exists(wait):
            account = account_tag_control.GetParentControl().GetChildren()[-1].Name
            self._wx.ChatBox.ButtonControl(Name='').Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            return account
        else:
            self._wx.ChatBox.ButtonControl(Name='').Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        

class ContactWnd:
    _clsname = 'ContactManagerWindow'

    def __init__(self):
        self.UiaAPI = uia.WindowControl(ClassName=self._clsname, searchDepth=1)
        self.Sidebar, _, self.ContactBox = self.UiaAPI.PaneControl(ClassName='', searchDepth=3, foundIndex=3).GetChildren()

    def __repr__(self) -> str:
        return f"<wxauto Contact Window at {hex(id(self))}>"

    def _show(self):
        self.HWND = FindWindow(classname=self._clsname)
        win32gui.ShowWindow(self.HWND, 1)
        win32gui.SetWindowPos(self.HWND, -1, 0, 0, 0, 0, 3)
        win32gui.SetWindowPos(self.HWND, -2, 0, 0, 0, 0, 3)
        self.UiaAPI.SwitchToThisWindow()

    def GetFriendNum(self):
        """获取好友人数"""
        wxlog.debug('获取好友人数')
        numText = self.Sidebar.PaneControl(Name='全部').TextControl(foundIndex=2).Name
        return int(re.findall('\d+', numText)[0])
    
    def Search(self, keyword):
        """搜索好友

        Args:
            keyword (str): 搜索关键词
        """
        wxlog.debug(f"搜索好友：{keyword}")
        if WxParam.MOUSE_MOVE:
            self._show()
        self.ContactBox.EditControl(Name="搜索").Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        self.ContactBox.ShortcutSelectAll(click=False)
        self.ContactBox.Input(keyword)

    def GetAllFriends(self, speed: int = 5):
        """获取好友列表
        
        Args:
            speed (int, optional): 滚动速度，数值越大滚动越快，但是太快可能导致遗漏，建议速度1-5之间
            
        Returns:
            list: 好友列表
        """
        wxlog.debug("获取好友列表")
        if WxParam.MOUSE_MOVE:
            self._show()
        
        contacts_list = []

        contact_ele_list = self.ContactBox.ListControl().GetChildren()

        n = 0
        idx = 0
        while n < 5:
            for _, ele in enumerate(contact_ele_list):
                contacts_info = {
                    'nickname': ele.TextControl().Name.replace('</em>', '').replace('<em>', ''),
                    'remark': ele.ButtonControl(foundIndex=2).Name.replace('</em>', '').replace('<em>', ''),
                    'tags': ele.ButtonControl(foundIndex=3).Name.replace('</em>', '').replace('<em>', '').split('，'),
                }
                if contacts_info.get('remark') in ('添加备注', ''):
                    contacts_info['remark'] = None
                if contacts_info.get('tags') in (['添加标签'], ['']):
                    contacts_info['tags'] = None
                # if contacts_info not in contacts_list:
                contacts_list.append(contacts_info)

            lastid = ele.GetRuntimeId()
            top_ele = ele.BoundingRectangle.top

            n = 0
            while n < 5:
                nowlist = [i.GetRuntimeId() for i in self.ContactBox.ListControl().GetChildren()]
                if lastid != nowlist[-1] and lastid in nowlist and top_ele == ele.BoundingRectangle.top:
                    break

                if top_ele == ele.BoundingRectangle.top:
                    self.ContactBox.WheelDown(wheelTimes=speed)
                    time.sleep(0.01)
                    n += 1
                top_ele = ele.BoundingRectangle.top

            while True:
                nowlist = [i.GetRuntimeId() for i in self.ContactBox.ListControl().GetChildren()]
                if lastid in nowlist:
                    break
                time.sleep(0.01)
            idx = nowlist.index(lastid) + 1
            contact_ele_list = self.ContactBox.ListControl().GetChildren()[idx:]
        return contacts_list
    
    def GetAllRecentGroups(self, speed: int = 1, wait=0.05):
        """获取群列表
        
        Args:
            speed (int, optional): 滚动速度，数值越大滚动越快，但是太快可能导致遗漏，建议速度1-3之间
            wait (float, optional): 滚动等待时间，建议和speed一起调整，直至适合你电脑配置和微信群数量达到平衡，不遗漏数据
            
        Returns:
            list: 群列表
        """
        if WxParam.MOUSE_MOVE:
            self._show()
        self.UiaAPI.PaneControl(Name='最近群聊').Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        group_list_control = self.UiaAPI.PaneControl(Name='最近群聊').GetParentControl().ListControl()
        groups = []

        n = 0
        idx = 0
        group_list_items = group_list_control.GetChildren()
        while n < 5:
            for _, item in enumerate(group_list_items):
                text_control1, text_control2 = item.TextControl().GetParentControl().GetChildren()
                group_name = text_control1.Name
                group_members = text_control2.Name.strip('(').strip(')')
                groups.append((group_name, group_members))

            lastid = item.GetRuntimeId()
            top_ele = item.BoundingRectangle.top

            n = 0
            while n < 5:
                nowlist = [i.GetRuntimeId() for i in group_list_control.GetChildren()]
                if lastid != nowlist[-1] and lastid in nowlist and top_ele == item.BoundingRectangle.top:
                    break

                if top_ele == item.BoundingRectangle.top:
                    group_list_control.WheelDown(wheelTimes=speed)
                    time.sleep(wait)
                    n += 1
                top_ele = item.BoundingRectangle.top

            while True:
                nowlist = [i.GetRuntimeId() for i in group_list_control.GetChildren()]
                if lastid in nowlist:
                    break
                time.sleep(0.01)
            idx = nowlist.index(lastid) + 1
            group_list_items = group_list_control.GetChildren()[idx:]
        return groups
    
    def Close(self):
        """关闭联系人窗口"""
        wxlog.debug('关闭联系人窗口')
        
        self.UiaAPI.SendKeys('{Esc}')


class ContactElement:
    def __init__(self, ele):
        self.element = ele
        self.nickname = ele.TextControl().Name
        self.remark = ele.ButtonControl(foundIndex=2).Name
        self.tags = ele.ButtonControl(foundIndex=3).Name.split('，')

    def __repr__(self) -> str:
        return f"<wxauto Contact Element at {hex(id(self))} ({self.nickname}: {self.remark})>"
    
    def EditRemark(self, remark: str):
        """修改好友备注名
        
        Args:
            remark (str): 新备注名
        """
        wxlog.debug(f"修改好友备注名：{self.nickname} --> {remark}")
        self.element.ButtonControl(foundIndex=2).Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        self.element.ShortcutSelectAll(move=WxParam.MOUSE_MOVE)
        self.element.Input(remark)
        self.element.SendKeys('{Enter}')

class AddTalkMemberWnd:
    def __init__(self, wx) -> None:
        self._wx = wx
        self.UiaAPI = self._wx.UiaAPI.WindowControl(ClassName='AddTalkMemberWnd', searchDepth=3)
        self.searchbox = self.UiaAPI.EditControl(Name='搜索')

    def __repr__(self) -> str:
        return f"<wxauto Add Member Window at {hex(id(self))}>"
    
    def Search(self, keyword):
        """搜索好友
        
        Args:
            keyword (str): 搜索关键词
        """
        wxlog.debug(f"搜索好友：{keyword}")
        self.searchbox.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        self.searchbox.ShortcutSelectAll(move=WxParam.MOUSE_MOVE)
        self.searchbox.Input(keyword)
        time.sleep(0.5)
        result = self.UiaAPI.ListControl().GetChildren()
        return result
    
    def Add(self, keyword):
        """搜索并添加好友
        
        Args:
            keyword (str): 搜索关键词
        """
        result = self.Search(keyword)
        if len(result) == 1:
            result[0].ButtonControl().Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            wxlog.debug(f"添加好友：{keyword}")
        elif len(result) > 1:
            wxlog.warning(f"搜索到多个好友：{keyword}")
        else:
            wxlog.error(f"未找到好友：{keyword}")

    def Submit(self):
        self.UiaAPI.ButtonControl(Name='完成').Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        wxlog.debug("发起多人语音聊天")
        # confirmdlg = self.UiaAPI.WindowControl(ClassName='ConfirmDialog')

class AddMemberWnd:
    def __init__(self, wx) -> None:
        self._wx = wx
        self.UiaAPI = self._wx.UiaAPI.WindowControl(ClassName='AddMemberWnd', searchDepth=3)
        self.searchbox = self.UiaAPI.EditControl(Name='搜索')

    def __repr__(self) -> str:
        return f"<wxauto Add Member Window at {hex(id(self))}>"
    
    def Search(self, keyword):
        """搜索好友
        
        Args:
            keyword (str): 搜索关键词
        """
        wxlog.debug(f"搜索好友：{keyword}")
        # self.searchbox.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        # self.searchbox.ShortcutSelectAll(move=WxParam.MOUSE_MOVE)
        self.searchbox.Input(keyword)
        time.sleep(0.5)
        result = self.UiaAPI.ListControl(Name="请勾选需要添加的联系人").GetChildren()
        return result
    
    def Add(self, keyword):
        """搜索并添加好友
        
        Args:
            keyword (str): 搜索关键词
        """
        result = self.Search(keyword)
        if len(result) == 1:
            result[0].ButtonControl().Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            wxlog.debug(f"添加好友：{keyword}")
        elif len(result) > 1:
            wxlog.warning(f"搜索到多个好友：{keyword}")
        else:
            wxlog.error(f"未找到好友：{keyword}")

    def Submit(self):
        self.UiaAPI.ButtonControl(Name='完成').Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        wxlog.debug("提交添加好友请求")
        confirmdlg = self.UiaAPI.WindowControl(ClassName='ConfirmDialog')
        t0 = time.time()
        while True:
            if time.time() - t0 > 5:
                raise TimeoutError("新增群好友等待超时")
            if not self.UiaAPI.Exists(0.1):
                wxlog.debug("新增群好友成功，无须再次确认")
                return
            if confirmdlg.Exists(0.1):
                wxlog.debug("新增群好友成功，确认添加")
                time.sleep(1)
                # confirmdlg.ButtonControl(Name='确定').Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                confirmdlg.SendKeys('{ENTER}')
                return

    def Close(self):
        self.UiaAPI.SendKeys('{ESC}')
        
class GroupMemberElement:
    def __init__(self, ele, wx) -> None:
        self.UiaAPI = ele
        self._wx = wx

    def __repr__(self) -> str:
        return f"<wxauto Group Member Element at {hex(id(self))}>"
    
    @property
    def nickname(self):
        return self.UiaAPI.Name
    
    def add_friend(self, addmsg=None, remark=None, tags=None, permission='朋友圈'):
        """添加新的好友

        Args:
            addmsg (str, optional): 添加好友的消息
            remark (str, optional): 备注名
            tags (list, optional): 标签列表
            permission (str, optional): 朋友圈权限, 可选值：'朋友圈', '仅聊天'

        Returns:
            int
            0 - 添加失败
            1 - 发送请求成功
            2 - 已经是好友
            3 - 对方不允许通过群聊添加好友
                
        Example:
            >>> addmsg = '你好，我是xxxx'      # 添加好友的消息
            >>> remark = '备注名字'            # 备注名
            >>> tags = ['朋友', '同事']        # 标签列表
            >>> msg.add_friend(keywords, addmsg=addmsg, remark=remark, tags=tags)
        """
        returns = {
            '添加失败': 0,
            '发送请求成功': 1,
            '已经是好友': 2,
            '对方不允许通过群聊添加好友': 3
        }
        # self._wx._show()
        roominfoWnd = self._wx.UiaAPI.Control(ClassName='SessionChatRoomDetailWnd', searchDepth=1)
        RollIntoView(roominfoWnd, self.UiaAPI, equal=True)
        self.UiaAPI.Click(simulateMove=False, move=True)
        contactwnd = self._wx.UiaAPI.PaneControl(ClassName='ContactProfileWnd')
        if not contactwnd.Exists(1):
            return returns['添加失败']
        addbtn = contactwnd.ButtonControl(Name='添加到通讯录')
        isfriend = not addbtn.Exists(0.2)
        if isfriend:
            contactwnd.SendKeys('{Esc}')
            return returns['已经是好友']
        else:
            addbtn.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            NewFriendsWnd = self._wx.UiaAPI.WindowControl(ClassName='WeUIDialog')
            AlertWnd = self._wx.UiaAPI.WindowControl(ClassName='AlertDialog')

            t0 = time.time()
            status = 0
            while time.time() - t0 < 5:
                if NewFriendsWnd.Exists(0.1):
                    status = 1
                    break
                elif AlertWnd.Exists(0.1):
                    status = 2
                    break
            
            if status == 0:
                return returns['添加失败']
            elif status == 2:
                AlertWnd.ButtonControl().Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                return returns['对方不允许通过群聊添加好友']
            elif status == 1:
                tipscontrol = NewFriendsWnd.TextControl(Name="你的联系人较多，添加新的朋友时需选择权限")

                permission_sns = NewFriendsWnd.CheckBoxControl(Name='聊天、朋友圈、微信运动等')
                permission_chat = NewFriendsWnd.CheckBoxControl(Name='仅聊天')
                if tipscontrol.Exists(0.5):
                    permission_sns = tipscontrol.GetParentControl().GetParentControl().TextControl(Name='朋友圈')
                    permission_chat = tipscontrol.GetParentControl().GetParentControl().TextControl(Name='仅聊天')

                if addmsg:
                    msgedit = NewFriendsWnd.TextControl(Name="发送添加朋友申请").GetParentControl().EditControl()
                    msgedit.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                    msgedit.ShortcutSelectAll(move=WxParam.MOUSE_MOVE)
                    msgedit.Input(addmsg)

                if remark:
                    remarkedit = NewFriendsWnd.TextControl(Name='备注名').GetParentControl().EditControl()
                    remarkedit.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                    remarkedit.ShortcutSelectAll(move=WxParam.MOUSE_MOVE)
                    remarkedit.Input(remark)

                if tags:
                    tagedit = NewFriendsWnd.TextControl(Name='标签').GetParentControl().EditControl()
                    for tag in tags:
                        tagedit.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                        tagedit.Input(tag)
                        NewFriendsWnd.PaneControl(ClassName='DropdownWindow').TextControl().Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                
                if permission == '朋友圈':
                    permission_sns.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                elif permission == '仅聊天':
                    permission_chat.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)

                # while NewFriendsWnd.Exists(0.3):
                NewFriendsWnd.ButtonControl(Name='确定').Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                return returns['发送请求成功']
            return returns['添加失败']

class SessionElement:
    def __init__(self, item):
        self.name = item.GetProgenyControl(4, control_type='TextControl').Name\
            if item.GetProgenyControl(4, control_type='TextControl') else None
        self.time = item.GetProgenyControl(4, 1, control_type='TextControl').Name\
            if item.GetProgenyControl(4, 1, control_type='TextControl') else None
        self.content = item.GetProgenyControl(4, 2, control_type='TextControl').Name\
            if item.GetProgenyControl(4, 2, control_type='TextControl') else None
        self.isnew = item.GetProgenyControl(2, 2) is not None
        wxlog.debug(f"============== 【{self.name}】 ==============")
        wxlog.debug(f"最后一条消息时间: {self.time}")
        wxlog.debug(f"最后一条消息内容: {self.content}")
        wxlog.debug(f"是否有新消息: {self.isnew}")


class Message:
    type = 'message'

    def __getitem__(self, index):
        return self.info[index]
    
    def __str__(self):
        return self.content
    
    def __repr__(self):
        return str(self.info[:2])
    
    @property
    def details(self):
        if hasattr(self, '_details'):
            return self._details
        chat_info = {
            'id': self.id,
            'type': self.type,
            'sender': self.sender,
            'content': self.content,
        }
        if self.type == 'time':
            chat_info['time'] = self.time
        elif self.type == 'friend':
            chat_info['sender_remark'] = self.sender_remark
        if self.chatbox.PaneControl(ClassName='popupshadow').Exists(0):
            chat_name_control = self.chatbox.GetProgenyControl(12)
        else:
            chat_name_control = self.chatbox.GetProgenyControl(11)
        chat_name_control_list = chat_name_control.GetParentControl().GetChildren()
        chat_name_control_count = len(chat_name_control_list)
        if chat_name_control_count == 1:
            if self.chatbox.ButtonControl(Name='公众号主页').Exists(0):
                chat_info['chat_type'] = 'official'
            else:
                chat_info['chat_type'] = 'friend'
            chat_info['chat_name'] = chat_name_control.Name
        elif chat_name_control_count == 2:
            chat_info['chat_type'] = 'group'
            chat_info['chat_name'] = chat_name_control.Name.replace(chat_name_control_list[-1].Name, '')
            chat_info['group_member_count'] = int(chat_name_control_list[-1].Name.replace('(', '').replace(')', ''))

            ori_chat_name_control = chat_name_control.GetParentControl().GetParentControl().TextControl(searchDepth=1)
            if ori_chat_name_control.Exists(0):
                chat_info['chat_remark'] = chat_info['chat_name']
                chat_info['chat_name'] = ori_chat_name_control.Name
        self._details = chat_info
        return self._details
    

class SysMessage(Message):
    type = 'sys'
    
    def __init__(self, info, control, wx):
        self.info = info
        self.control = control
        self.wx = wx
        self.sender = info[0]
        self.content = info[1]
        self.id = info[-1]
        _is_main_window = hasattr(wx, 'ChatBox')
        self.chatbox = wx.ChatBox if _is_main_window else wx.UiaAPI
        
        wxlog.debug(f"【系统消息】{self.content}")
    
    # def __repr__(self):
    #     return f'<wxauto SysMessage at {hex(id(self))}>'
    

class TimeMessage(Message):
    type = 'time'
    
    def __init__(self, info, control, wx):
        self.info = info
        self.control = control
        self.wx = wx
        self.time = ParseWeChatTime(info[1])
        self.sender = info[0]
        self.content = info[1]
        self.id = info[-1]
        _is_main_window = hasattr(wx, 'ChatBox')
        self.chatbox = wx.ChatBox if _is_main_window else wx.UiaAPI
        
        wxlog.debug(f"【时间消息】{self.time}")
    
    # def __repr__(self):
    #     return f'<wxauto TimeMessage at {hex(id(self))}>'
    

class RecallMessage(Message):
    type = 'recall'
    
    def __init__(self, info, control, wx):
        self.info = info
        self.control = control
        self.wx = wx
        self.sender = info[0]
        self.content = info[1]
        self.id = info[-1]
        _is_main_window = hasattr(wx, 'ChatBox')
        self.chatbox = wx.ChatBox if _is_main_window else wx.UiaAPI
        
        wxlog.debug(f"【撤回消息】{self.content}")
    
    # def __repr__(self):
    #     return f'<wxauto RecallMessage at {hex(id(self))}>'
    

class SelfMessage(Message):
    type = 'self'
    
    def __init__(self, info, control, obj):
        self.info = info
        self.control = control
        self._winobj = obj
        self.sender = info[0]
        self.content = info[1]
        self.id = info[-1]
        _is_main_window = hasattr(obj, 'ChatBox')
        self.chatbox = obj.ChatBox if _is_main_window else obj.UiaAPI
        
        wxlog.debug(f"【自己消息】{self.content}")
    
    # def __repr__(self):
    #     return f'<wxauto SelfMessage at {hex(id(self))}>'

    def quote(self, msg, at=None):
        """引用该消息

        Args:
            msg (str): 引用的消息内容

        Returns:
            bool: 是否成功引用
        """
        wxlog.debug(f'发送引用消息：{msg}  --> {self.sender} | {self.content}')
        self._winobj._show()
        headcontrol = [i for i in self.control.GetFirstChildControl().GetChildren() if i.ControlTypeName == 'ButtonControl'][0]
        RollIntoView(self.chatbox.ListControl(), headcontrol, equal=True)
        xbias = int(headcontrol.BoundingRectangle.width()*1.5)
        headcontrol.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        headcontrol.RightClick(x=-xbias, simulateMove=False)
        menu = self._winobj.UiaAPI.MenuControl(ClassName='CMenuWnd')
        quote_option = menu.MenuItemControl(Name="引用")
        if not quote_option.Exists(maxSearchSeconds=0.1):
            wxlog.debug('该消息当前状态无法引用')
            return False
        quote_option.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        editbox = self.chatbox.EditControl(searchDepth=15)
        t0 = time.time()
        while True:
            if time.time() - t0 > 10:
                raise TimeoutError(f'发送消息超时 --> {msg}')
            SetClipboardText(msg)
            editbox.ShortcutPaste(move=WxParam.MOUSE_MOVE)
            if editbox.GetValuePattern().Value.replace('\r￼', ''):
                break
        
        if at:
            if isinstance(at, str):
                at = [at]
            for i in at:
                editbox.Input('@'+i)
                atwnd = self._winobj.UiaAPI.PaneControl(ClassName='ChatContactMenu')
                if atwnd.Exists(maxSearchSeconds=0.1):
                    self._winobj.UiaAPI.SendKeys('{ENTER}')

        time.sleep(0.1)
        editbox.SendKeys(WxParam.SHORTCUT_SEND)
        # headcontrol.RightClick()
        return True
    
    def parse_url(self, timeout=10):
        """解析消息中的链接

        Args:
            timeout (int, optional): 超时时间

        Returns:
            str: 链接地址
        """
        if self.content not in ('[链接]', '[音乐]'):
            return None
        if self.content == '[链接]' and (
            self.control.TextControl(Name="邀请你加入群聊").Exists(0)\
            or self.control.TextControl(Name="Group Chat Invitation").Exists(0)):
            return '[链接](群聊邀请)'
        if not self.control.PaneControl().Exists(0):
            return None
        link_control_list = self.control.PaneControl().GetChildren()
        if len(link_control_list) < 2:
            return None
        link_control = link_control_list[1]
        if not link_control.ButtonControl().Exists(0):
            return None

        self.control.TextControl().Click()
        t0 = time.time()
        while not FindWindow('Chrome_WidgetWin_0', '微信'):
            if time.time() - t0 > timeout:
                raise TimeoutError('Open url timeout')
            time.sleep(0.01)
        wxbrowser = uia.PaneControl(ClassName="Chrome_WidgetWin_0", Name="微信", searchDepth=1)

        while not wxbrowser.DocumentControl().GetChildren():
            if time.time() - t0 > timeout:
                raise TimeoutError('Open url timeout')
            time.sleep(0.01)

        wxbrowser.PaneControl(searchDepth=1, ClassName='').MenuItemControl(Name="更多").Click()
        wxbrowser = uia.PaneControl(ClassName="Chrome_WidgetWin_0", Name="微信", searchDepth=1)
        copyurl = wxbrowser.PaneControl(ClassName='Chrome_WidgetWin_0').MenuItemControl(Name='复制链接')
        copyurl.Click()
        url = ReadClipboardData()['13']
        wxbrowser.PaneControl(searchDepth=1, ClassName='').ButtonControl(Name="关闭").Click()
        return url
    
    def forward(self, friend):
        """转发该消息
        
        Args:
            friend (str): 转发给的好友昵称、备注或微信号
        
        Returns:
            bool: 是否成功转发
        """
        wxlog.debug(f'转发消息：{self.sender} --> {friend} | {self.content}')
        self._winobj._show()
        headcontrol = [i for i in self.control.GetFirstChildControl().GetChildren() if i.ControlTypeName == 'ButtonControl'][0]
        RollIntoView(self.chatbox.ListControl(), headcontrol, equal=True)
        xbias = int(headcontrol.BoundingRectangle.width()*1.5)
        headcontrol.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        headcontrol.RightClick(x=-xbias, simulateMove=False)
        menu = self._winobj.UiaAPI.MenuControl(ClassName='CMenuWnd')
        forward_option = menu.MenuItemControl(Name="转发...")
        if not forward_option.Exists(maxSearchSeconds=0.1):
            wxlog.debug('该消息当前状态无法转发')
            return False
        forward_option.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        SetClipboardText(friend)
        contactwnd = self._winobj.UiaAPI.WindowControl(ClassName='SelectContactWnd')
        edit = contactwnd.EditControl()
        while not edit.HasKeyboardFocus:
            edit.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            time.sleep(0.1)
        edit.ShortcutSelectAll(move=WxParam.MOUSE_MOVE)
        edit.ShortcutPaste(move=WxParam.MOUSE_MOVE)
        checkbox = contactwnd.ListControl().CheckBoxControl()
        if checkbox.Exists(1):
            checkbox.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            contactwnd.ButtonControl(Name='发送').Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            return True
        else:
            contactwnd.SendKeys('{Esc}')
            raise FriendNotFoundError(f'未找到好友：{friend}')
    
    def parse(self):
        """解析合并消息内容，当且仅当消息内容为合并转发的消息时有效"""
        wxlog.debug(f'解析合并消息内容：{self.sender} | {self.content}')
        self._winobj._show()
        headcontrol = [i for i in self.control.GetFirstChildControl().GetChildren() if i.ControlTypeName == 'ButtonControl'][0]
        RollIntoView(self.chatbox.ListControl(), headcontrol, equal=True)
        xbias = int(headcontrol.BoundingRectangle.width()*1.5)
        headcontrol.Click(x=-xbias, simulateMove=False)
        chatrecordwnd = ChatRecordWnd()
        time.sleep(2)
        msgs = chatrecordwnd.GetContent()
        
        # chatrecordwnd = uia.WindowControl(ClassName='ChatRecordWnd', searchDepth=1)
        # msgitems = chatrecordwnd.ListControl().GetChildren()
        # msgs = []
        # for msgitem in msgitems:
        #     textcontrols = [i for i in GetAllControl(msgitem) if i.ControlTypeName == 'TextControl']
        #     who = textcontrols[0].Name
        #     time = textcontrols[1].Name
        #     try:
        #         content = textcontrols[2].Name
        #     except IndexError:
        #         content = ''
        #     msgs.append(([who, content, ParseWeChatTime(time)]))
        # chatrecordwnd.SendKeys('{Esc}')
        return msgs

class FriendMessage(Message):
    type = 'friend'
    
    def __init__(self, info, control, obj):
        self.info = info
        self.control = control
        self._winobj = obj
        self.sender = info[0][0]
        self.sender_remark = info[0][1]
        self.content = info[1]
        self.id = info[-1]
        self.info[0] = info[0][0]
        _is_main_window = hasattr(obj, 'ChatBox')
        self.chatbox = obj.ChatBox if _is_main_window else obj.UiaAPI
        
        if self.sender == self.sender_remark:
            wxlog.debug(f"【好友消息】{self.sender}: {self.content}")
        else:
            wxlog.debug(f"【好友消息】{self.sender}({self.sender_remark}): {self.content}")
    
    # def __repr__(self):
    #     return f'<wxauto FriendMessage at {hex(id(self))}>'

    def quote(self, msg, at=None):
        """引用该消息

        Args:
            msg (str): 引用的消息内容

        Returns:
            bool: 是否成功引用
        """
        wxlog.debug(f'发送引用消息：{msg}  --> {self.sender} | {self.content}')
        self._winobj._show()
        headcontrol = [i for i in self.control.GetFirstChildControl().GetChildren() if i.ControlTypeName == 'ButtonControl'][0]
        RollIntoView(self.chatbox.ListControl(), headcontrol, equal=False)
        xbias = int(headcontrol.BoundingRectangle.width()*1.5)
        headcontrol.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        headcontrol.RightClick(x=xbias, simulateMove=False)
        menu = self._winobj.UiaAPI.MenuControl(ClassName='CMenuWnd')
        quote_option = menu.MenuItemControl(Name="引用")
        if not quote_option.Exists(maxSearchSeconds=0.1):
            wxlog.debug('该消息当前状态无法引用')
            return False
        quote_option.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        editbox = self.chatbox.EditControl(searchDepth=15)
        t0 = time.time()
        while True:
            if time.time() - t0 > 10:
                raise TimeoutError(f'发送消息超时 --> {msg}')
            SetClipboardText(msg)
            editbox.ShortcutPaste(move=WxParam.MOUSE_MOVE)
            if editbox.GetValuePattern().Value.replace('\r￼', ''):
                break

        if at:
            if isinstance(at, str):
                at = [at]
            for i in at:
                editbox.Input('@'+i)
                atwnd = self._winobj.UiaAPI.PaneControl(ClassName='ChatContactMenu')
                if atwnd.Exists(maxSearchSeconds=0.1):
                    self._winobj.UiaAPI.SendKeys('{ENTER}')

        time.sleep(0.1)
        editbox.SendKeys(WxParam.SHORTCUT_SEND)
        return True
    
    def parse_url(self, timeout=10):
        """解析消息中的链接

        Args:
            timeout (int, optional): 超时时间

        Returns:
            str: 链接地址
        """
        if self.content not in ('[链接]', '[音乐]'):
            return None
        if self.content == '[链接]' and (
            self.control.TextControl(Name="邀请你加入群聊").Exists(0)\
            or self.control.TextControl(Name="Group Chat Invitation").Exists(0)):
            return '[链接](群聊邀请)'
        if not self.control.PaneControl().Exists(0):
            return None
        link_control_list = self.control.PaneControl().GetChildren()
        if len(link_control_list) < 2:
            return None
        link_control = link_control_list[1]
        if not link_control.ButtonControl().Exists(0):
            return None

        self.control.TextControl().Click()
        t0 = time.time()
        while not FindWindow('Chrome_WidgetWin_0', '微信'):
            if time.time() - t0 > timeout:
                raise TimeoutError('Open url timeout')
            time.sleep(0.01)
        wxbrowser = uia.PaneControl(ClassName="Chrome_WidgetWin_0", Name="微信", searchDepth=1)

        while not wxbrowser.DocumentControl().GetChildren():
            if time.time() - t0 > timeout:
                raise TimeoutError('Open url timeout')
            time.sleep(0.01)

        wxbrowser.PaneControl(searchDepth=1, ClassName='').MenuItemControl(Name="更多").Click()
        wxbrowser = uia.PaneControl(ClassName="Chrome_WidgetWin_0", Name="微信", searchDepth=1)
        copyurl = wxbrowser.PaneControl(ClassName='Chrome_WidgetWin_0').MenuItemControl(Name='复制链接')
        copyurl.Click()
        url = ReadClipboardData()['13']
        wxbrowser.PaneControl(searchDepth=1, ClassName='').ButtonControl(Name="关闭").Click()
        return url
    
    def forward(self, friend):
        """转发该消息
        
        Args:
            friend (str): 转发给的好友昵称、备注或微信号
        
        Returns:
            bool: 是否成功转发
        """
        wxlog.debug(f'转发消息：{self.sender} --> {friend} | {self.content}')
        # self._winobj._show()
        headcontrol = [i for i in self.control.GetFirstChildControl().GetChildren() if i.ControlTypeName == 'ButtonControl'][0]
        RollIntoView(self.chatbox.ListControl(), headcontrol, equal=True)
        xbias = int(headcontrol.BoundingRectangle.width()*1.5)
        headcontrol.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        headcontrol.RightClick(x=xbias, simulateMove=False)
        menu = self._winobj.UiaAPI.MenuControl(ClassName='CMenuWnd')
        forward_option = menu.MenuItemControl(Name="转发...")
        if not forward_option.Exists(maxSearchSeconds=0.1):
            wxlog.debug('该消息当前状态无法转发')
            return False
        forward_option.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        SetClipboardText(friend)
        contactwnd = self._winobj.UiaAPI.WindowControl(ClassName='SelectContactWnd')
        edit = contactwnd.EditControl()
        while not edit.HasKeyboardFocus:
            edit.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            time.sleep(0.1)
        edit.ShortcutSelectAll(move=WxParam.MOUSE_MOVE)
        edit.ShortcutPaste(move=WxParam.MOUSE_MOVE)
        checkbox = contactwnd.ListControl().CheckBoxControl()
        if checkbox.Exists(1):
            checkbox.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            contactwnd.ButtonControl(Name='发送').Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            return True
        else:
            contactwnd.SendKeys('{Esc}')
            raise FriendNotFoundError(f'未找到好友：{friend}')
    
    def parse(self):
        """解析合并消息内容，当且仅当消息内容为合并转发的消息时有效"""
        wxlog.debug(f'解析合并消息内容：{self.sender} | {self.content}')
        # self._winobj._show()
        headcontrol = [i for i in self.control.GetFirstChildControl().GetChildren() if i.ControlTypeName == 'ButtonControl'][0]
        RollIntoView(self.chatbox.ListControl(), headcontrol, equal=True)
        xbias = int(headcontrol.BoundingRectangle.width()*1.5)
        headcontrol.Click(x=xbias, simulateMove=False)
        chatrecordwnd = ChatRecordWnd()
        time.sleep(2)
        msgs = chatrecordwnd.GetContent()
        # chatrecordwnd = uia.WindowControl(ClassName='ChatRecordWnd', searchDepth=1)
        # msgitems = chatrecordwnd.ListControl().GetChildren()
        # msgs = []
        # for msgitem in msgitems:
        #     textcontrols = [i for i in GetAllControl(msgitem) if i.ControlTypeName == 'TextControl']
        #     who = textcontrols[0].Name
        #     time = textcontrols[1].Name
        #     try:
        #         content = textcontrols[2].Name
        #     except IndexError:
        #         content = ''
        #     msgs.append(([who, content, ParseWeChatTime(time)]))
        # chatrecordwnd.SendKeys('{Esc}')
        return msgs
    
    def sender_info(self):
        """获取好友信息"""
        wxlog.debug(f"获取好友信息：{self.sender}")
        if hasattr(self, 'contact_info'):
            return self.contact_info
        # contact_info = {
        #     "nickname": None,
        #     "id": None,
        #     "remark": None,
        #     "tags": None,
        #     "source": None,
        #     "signature": None,
        # }
        
        self._winobj._show()
        headcontrol = [i for i in self.control.GetFirstChildControl().GetChildren() if i.ControlTypeName == 'ButtonControl'][0]
        RollIntoView(self.chatbox.ListControl(), headcontrol, equal=True)
        headcontrol.Click(simulateMove=False, move=WxParam.MOUSE_MOVE, show_window=(not WxParam.MOUSE_MOVE))
        profile = ProfileWnd(self._winobj)
        self.contact_info = profile.contact_info
        profile.Close()
        return self.contact_info
        # contactwnd = self._winobj.UiaAPI.PaneControl(ClassName='ContactProfileWnd')
        # if not contactwnd.Exists(1):
        #     return 
        
        # def extract_info(contactwnd):
        #     if contactwnd.ControlTypeName == "TextControl":
        #         text = contactwnd.Name
        #         if text.startswith("昵称："):
        #             sibling = contactwnd.GetNextSiblingControl()
        #             if sibling:
        #                 contact_info["nickname"] = sibling.Name.strip()
        #         elif text.startswith("微信号："):
        #             sibling = contactwnd.GetNextSiblingControl()
        #             if sibling:
        #                 contact_info["id"] = sibling.Name.strip()
        #         elif text.startswith("备注"):
        #             sibling = contactwnd.GetNextSiblingControl()
        #             if sibling and sibling.TextControl().Exists(0):
        #                 contact_info["remark"] = sibling.TextControl().Name.strip()
        #         elif text.startswith("标签"):
        #             sibling = contactwnd.GetNextSiblingControl()
        #             if sibling:
        #                 contact_info["tags"] = sibling.Name.strip()
        #         elif text.startswith("来源"):
        #             sibling = contactwnd.GetNextSiblingControl()
        #             if sibling:
        #                 contact_info["source"] = sibling.Name.strip()
        #         elif text.startswith("个性签名"):
        #             sibling = contactwnd.GetNextSiblingControl()
        #             if sibling:
        #                 contact_info["signature"] = sibling.Name.strip()

        #     for child in contactwnd.GetChildren():
        #         extract_info(child)
        # extract_info(contactwnd)
        # contactwnd.SendKeys('{Esc}')
        # return contact_info
    
    def modify(self, remark=None, tags=None):
        """修改好友信息

        Args:
            remark (str, optional): 备注名
            tags (list, optional): 标签列表

        Returns:
            bool: 是否修改成功
        """
        if all([not remark, not tags]):
            return False
        self._winobj._show()
        headcontrol = [i for i in self.control.GetFirstChildControl().GetChildren() if i.ControlTypeName == 'ButtonControl'][0]
        RollIntoView(self.chatbox.ListControl(), headcontrol, equal=True)
        headcontrol.Click(simulateMove=False, move=WxParam.MOUSE_MOVE, show_window=(not WxParam.MOUSE_MOVE))
        profile = ProfileWnd(self._winobj)
        self.contact_info = profile.contact_info
        result = profile.ModifyRemarkOrTags(remark, tags)
        profile.Close()
        return result


    
    def add_friend(self, addmsg=None, remark=None, tags=None, permission='朋友圈'):
        """添加新的好友

        Args:
            addmsg (str, optional): 添加好友的消息
            remark (str, optional): 备注名
            tags (list, optional): 标签列表
            permission (str, optional): 朋友圈权限, 可选值：'朋友圈', '仅聊天'

        Returns:
            int
            0 - 添加失败
            1 - 发送请求成功
            2 - 已经是好友
            3 - 对方不允许通过群聊添加好友
                
        Example:
            >>> addmsg = '你好，我是xxxx'      # 添加好友的消息
            >>> remark = '备注名字'            # 备注名
            >>> tags = ['朋友', '同事']        # 标签列表
            >>> msg.add_friend(keywords, addmsg=addmsg, remark=remark, tags=tags)
        """
        returns = {
            '添加失败': 0,
            '发送请求成功': 1,
            '已经是好友': 2,
            '对方不允许通过群聊添加好友': 3
        }
        self._winobj._show()
        headcontrol = [i for i in self.control.GetFirstChildControl().GetChildren() if i.ControlTypeName == 'ButtonControl'][0]
        RollIntoView(self.chatbox.ListControl(), headcontrol, equal=True)
        headcontrol.Click(simulateMove=False, move=True)
        contactwnd = self._winobj.UiaAPI.PaneControl(ClassName='ContactProfileWnd')
        if not contactwnd.Exists(1):
            return returns['添加失败']
        addbtn = contactwnd.ButtonControl(Name='添加到通讯录')
        isfriend = not addbtn.Exists(0.2)
        if isfriend:
            contactwnd.SendKeys('{Esc}')
            return returns['已经是好友']
        else:
            addbtn.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            if type(self._winobj) == ChatWnd:
                NewFriendsWnd = self._winobj._wx.UiaAPI.WindowControl(ClassName='WeUIDialog')
                AlertWnd = self._winobj._wx.UiaAPI.WindowControl(ClassName='AlertDialog')
            else:
                NewFriendsWnd = self._winobj.UiaAPI.WindowControl(ClassName='WeUIDialog')
                AlertWnd = self._winobj.UiaAPI.WindowControl(ClassName='AlertDialog')
            


            t0 = time.time()
            status = 0
            while time.time() - t0 < 5:
                if NewFriendsWnd.Exists(0.1):
                    status = 1
                    break
                elif AlertWnd.Exists(0.1):
                    status = 2
                    break
            
            if status == 0:
                return returns['添加失败']
            elif status == 2:
                AlertWnd.ButtonControl().Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                return returns['对方不允许通过群聊添加好友']
            elif status == 1:
                tipscontrol = NewFriendsWnd.TextControl(Name="你的联系人较多，添加新的朋友时需选择权限")

                permission_sns = NewFriendsWnd.CheckBoxControl(Name='聊天、朋友圈、微信运动等')
                permission_chat = NewFriendsWnd.CheckBoxControl(Name='仅聊天')
                if tipscontrol.Exists(0.5):
                    permission_sns = tipscontrol.GetParentControl().GetParentControl().TextControl(Name='朋友圈')
                    permission_chat = tipscontrol.GetParentControl().GetParentControl().TextControl(Name='仅聊天')

                if addmsg:
                    msgedit = NewFriendsWnd.TextControl(Name="发送添加朋友申请").GetParentControl().EditControl()
                    msgedit.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                    msgedit.ShortcutSelectAll(move=WxParam.MOUSE_MOVE)
                    msgedit.Input(addmsg)

                if remark:
                    remarkedit = NewFriendsWnd.TextControl(Name='备注名').GetParentControl().EditControl()
                    remarkedit.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                    remarkedit.ShortcutSelectAll(move=WxParam.MOUSE_MOVE)
                    remarkedit.Input(remark)

                if tags:
                    tagedit = NewFriendsWnd.TextControl(Name='标签').GetParentControl().EditControl()
                    for tag in tags:
                        tagedit.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                        tagedit.Input(tag)
                        NewFriendsWnd.PaneControl(ClassName='DropdownWindow').TextControl().Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)

                if permission == '朋友圈':
                    permission_sns.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                elif permission == '仅聊天':
                    permission_chat.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)

                NewFriendsWnd.ButtonControl(Name='确定').Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
                return returns['发送请求成功']
            return returns['添加失败']



message_types = {
    'SYS': SysMessage,
    'Time': TimeMessage,
    'Recall': RecallMessage,
    'Self': SelfMessage
}

def ParseMessage(data, control, wx):
    return message_types.get(data[0], FriendMessage)(data, control, wx)


class LoginWnd:
    _clsname = 'WeChatLoginWndForPC'

    def __init__(self):
        self.UiaAPI = uia.PaneControl(ClassName=self._clsname, searchDepth=1)

    def __repr__(self) -> str:
        return f"<wxauto LoginWnd Object at {hex(id(self))}>"

    def _show(self):
        self.HWND = FindWindow(name=self.who, classname=self._clsname)
        win32gui.ShowWindow(self.HWND, 1)
        win32gui.SetWindowPos(self.HWND, -1, 0, 0, 0, 0, 3)
        win32gui.SetWindowPos(self.HWND, -2, 0, 0, 0, 0, 3)
        self.UiaAPI.SwitchToThisWindow()

    @property
    def _app_path(self):
        HWND = FindWindow(classname=self._clsname)
        return GetPathByHwnd(HWND)

    def login(self):
        enter_button = self.UiaAPI.ButtonControl(Name='进入微信')
        if enter_button.Exists(0.5):
            enter_button.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
            return True

    def get_qrcode(self):
        """获取登录二维码
        
        Returns:
            str: 二维码图片的保存路径
        """
        self.reopen()
        switch_account_button = self.UiaAPI.ButtonControl(Name='切换账号')
        if switch_account_button.Exists(0.5):
            switch_account_button.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        
        qrcode_control = self.UiaAPI.ButtonControl(Name='二维码')
        qrcode = qrcode_control.ScreenShot()
        return qrcode
    
    def shutdown(self):
        """关闭进程"""
        pid = self.UiaAPI.ProcessId
        os.system(f'taskkill /f /pid {pid}')

    def reopen(self):
        """重新打开"""
        path = self._app_path
        self.shutdown()
        os.system(f'"start "" "{path}""')
        self.UiaAPI = uia.PaneControl(ClassName=self._clsname, searchDepth=1)

class WeChatMoments:
    _clsname = 'SnsWnd'

    def __init__(self, language='cn') -> None:
        self.language = language
        self.api = uia.WindowControl(ClassName=self._clsname, searchDepth=1)
        self.api.Exists(5)
        MainControl1 = [i for i in self.api.GetChildren() if not i.ClassName][0]
        self.ToolsBox = MainControl1.ToolBarControl(searchDepth=1)
        self.SnsBox = MainControl1.PaneControl(searchDepth=1)

        # Tools
        self.t_refresh = self.ToolsBox.ButtonControl(Name='刷新')

        self.GetMoments()

    def __repr__(self) -> str:
        return f'<WeChat Moments object at {hex(id(self))}>'

    def _show(self):
        self.HWND = FindWindow(classname=self._clsname)
        win32gui.ShowWindow(self.HWND, 1)
        win32gui.SetWindowPos(self.HWND, -1, 0, 0, 0, 0, 3)
        win32gui.SetWindowPos(self.HWND, -2, 0, 0, 0, 0, 3)
        self.api.SwitchToThisWindow()

    def Close(self):
        self.api.SendKeys('{ESC}')
    
    def Refresh(self):
        self.t_refresh.Click(simulateMove=False)

    def GetMoments(self, next_page=False, speed1=3, speed2=1):
        if next_page:
            while True:
                self.api.WheelDown(wheelTimes=speed1)
                moments_controls = [i for i in self.SnsBox.ListControl(Name='朋友圈').GetChildren() if i.ControlTypeName=='ListItemControl']
                moments = [Moments(i, self) for i in moments_controls]
                if [i.GetRuntimeId() for i in moments_controls][0] == self._ids[-1]:
                    break
                time.sleep(0.05)

            while True:
                self.api.WheelDown(wheelTimes=speed2)
                moments_controls = [i for i in self.SnsBox.ListControl(Name='朋友圈').GetChildren() if i.ControlTypeName=='ListItemControl']
                moments = [Moments(i, self) for i in moments_controls]
                if [i.GetRuntimeId() for i in moments_controls][0] != self._ids[-1]:
                    break
                time.sleep(0.01)

        moments_controls = [i for i in self.SnsBox.ListControl(Name='朋友圈').GetChildren() if i.ControlTypeName=='ListItemControl']
        moments = [Moments(i, self) for i in moments_controls]
        self._ids = [i.GetRuntimeId() for i in moments_controls]
        return moments

class Moments:
    def __init__(self, control: uia.Control, parent) -> None:
        self.api = control
        self.parent = parent
        self.language = parent.language
        self.cmt = self.api.ButtonControl(Name='评论')
        self._parse()
    
    def __repr__(self) -> str:
        return f'<Moments {self.content}>'
    
    def __getattr__(self, name):
        try:
            return self.info[name]
        except KeyError:
            raise AttributeError(f"'Sns' object has no attribute '{name}'")
    
    def _parse(self):
        self.info = {
            'type': 'moment',
            'id': ''.join([str(i) for i in self.api.GetRuntimeId()]),
            'sender': '',
            'content': '',
            'time': '',
            'img_count': 0,
            'comments': [],
            'addr': '',
            'likes': []
        }
        content_control = self.api.GetProgenyControl(4, control_type='TextControl')
        self.info['sender'] = self.api.GetProgenyControl(4, control_type='ButtonControl').Name
        self.info['content'] = content_control.Name if content_control else ''
        self.info['time'] = self.api.ButtonControl(Name='评论').GetParentControl().TextControl().Name
        img_info_control = self.api.PaneControl(RegexName='包含\d+张图片')
        if img_info_control.Exists(0):
            self._img_controls = img_info_control.GetChildren()
            self.info['img_count'] = len(self._img_controls)
        else:
            self.info['img_count'] = 0
            self._img_controls = []

        if self.api.ListControl(Name='评论').Exists(0):
            self.info['comments'] = [i.Name for i in self.api.ListControl(Name='评论').GetChildren()]

        if self.api.TextControl(Name='广告').Exists(0):
            self.info['type'] = 'advertise'

        for i in range(10):
            text_control = self.api.GetProgenyControl(5, i, control_type='ButtonControl')
            if not text_control:
                break
            text_height = text_control.BoundingRectangle.height()
            if text_height == 18 and not self.info['addr']:
                self.info['addr'] = text_control.Name
            # elif text_height == 22:
            #     self.info['sender'] = text_control.Name

        like_control = self.api.GetProgenyControl(6, 0, control_type='TextControl')
        if like_control:
            self.info['likes'] = like_control.Name.split('，')
        
    def _download_pic(self, msgitem, savepath=''):
        RollIntoView(self.parent.api.ListControl(), msgitem, bias=self.parent.ToolsBox.BoundingRectangle.height()*2)
        msgitem.Click(move=WxParam.MOUSE_MOVE, simulateMove=False, return_pos=False)
        imgobj = WeChatImage()
        save_path = imgobj.Save(savepath=savepath)
        imgobj.Close()
        return save_path
    
    def SaveImages(self, save_index=None, save_path=''):
        """保存图片
        
        Args:
            save_index (int|list): 保存第几张图片（从0开始），默认为None，保存所有图片
            save_path (str): 绝对路径，包括文件名和后缀，例如："D:/Images/微信图片_xxxxxx.jpg"
                        （如果不填，则默认为当前脚本文件夹下，新建一个“微信图片(或视频)”的文件夹，保存在该文件夹内）
        """
        images = []
        if save_index:
            if isinstance(save_index, int):
                save_index = [save_index]
            elif not isinstance(save_index, list):
                raise TypeError("save_index must be int or list")

        for i, msgitem in enumerate(self._img_controls):
            if save_index and i not in save_index:
                continue
            imgpath = self._download_pic(msgitem, savepath=save_path)
            images.append(imgpath)
        return images
            
    def Like(self, like=True):
        RollIntoView(self.parent.SnsBox, self.cmt)
        self.cmt.Click(simulateMove=False)
        like_btn = self.parent.api.PaneControl(ClassName='SnsLikeToastWnd').ButtonControl(Name='赞')
        cancel_btn = self.parent.api.PaneControl(ClassName='SnsLikeToastWnd').ButtonControl(Name='取消')
        if like and like_btn.Exists(0):
            like_btn.Click(simulateMove=False)
        elif not like and cancel_btn.Exists(0):
            cancel_btn.Click(simulateMove=False)

    def Comment(self, text):
        self.cmt.Click(simulateMove=False)
        cmt_btn = self.parent.api.PaneControl(ClassName='SnsLikeToastWnd').ButtonControl(Name='评论')
        cmt_btn.Click(simulateMove=False)
        edit_control = self.parent.api.EditControl(Name='评论')
        SetClipboardText(text)
        edit_control.ShortcutPaste(click=True)
        edit_control.GetParentControl().ButtonControl(Name='发送').Click(simulateMove=False)

    def sender_info(self):
        
        contact_info = {
            "nickname": None,
            "id": None,
            "remark": None,
            "tags": None,
            "source": None,
            "signature": None,
        }
        
        self.parent._show()
        headcontrol = self.api.ButtonControl(Name=self.sender)
        RollIntoView(self.parent.api.ListControl(), headcontrol, equal=True, bias=self.parent.ToolsBox.BoundingRectangle.height()*2)
        headcontrol.Click(simulateMove=False, move=WxParam.MOUSE_MOVE, show_window=(not WxParam.MOUSE_MOVE))
        contactwnd = self.parent.api.PaneControl(ClassName='ContactProfileWnd')
        if not contactwnd.Exists(1):
            return 
        contact_info["nickname"] = contactwnd.ButtonControl().Name
        def extract_info(contactwnd):
            if contactwnd.ControlTypeName == "TextControl":
                text = contactwnd.Name
                if text.startswith("昵称："):
                    sibling = contactwnd.GetNextSiblingControl()
                    if sibling:
                        contact_info["nickname"] = sibling.Name.strip()
                elif text.startswith("微信号："):
                    sibling = contactwnd.GetNextSiblingControl()
                    if sibling:
                        contact_info["id"] = sibling.Name.strip()
                elif text.startswith("备注"):
                    sibling = contactwnd.GetNextSiblingControl()
                    if sibling and sibling.TextControl().Exists(0):
                        contact_info["remark"] = sibling.TextControl().Name.strip()
                elif text.startswith("标签"):
                    sibling = contactwnd.GetNextSiblingControl()
                    if sibling:
                        contact_info["tags"] = sibling.Name.strip()
                elif text.startswith("来源"):
                    sibling = contactwnd.GetNextSiblingControl()
                    if sibling:
                        contact_info["source"] = sibling.Name.strip()
                elif text.startswith("个性签名"):
                    sibling = contactwnd.GetNextSiblingControl()
                    if sibling:
                        contact_info["signature"] = sibling.Name.strip()

            for child in contactwnd.GetChildren():
                extract_info(child)
        extract_info(contactwnd)
        contactwnd.SendKeys('{Esc}')
        return contact_info
    
class ProfileWnd:
    _clsname = 'ContactProfileWnd'

    def __init__(self, parent):
        self.api = parent.UiaAPI.PaneControl(ClassName=self._clsname)
        # PrintAllControlTree(self.api)
        self.contact_info = {
            "nickname": None,
            "id": None,
            "remark": None,
            "tags": None,
            "source": None,
            "signature": None,
        }
        self._extract_info(self.api)

    def _extract_info(self, contactwnd):
        if contactwnd.ControlTypeName == "TextControl":
            text = contactwnd.Name
            if text.startswith("昵称："):
                sibling = contactwnd.GetNextSiblingControl()
                if sibling:
                    self.contact_info["nickname"] = sibling.Name.strip()
            elif text.startswith("微信号："):
                sibling = contactwnd.GetNextSiblingControl()
                if sibling:
                    self.contact_info["id"] = sibling.Name.strip()
            elif text.startswith("群昵称："):
                sibling = contactwnd.GetNextSiblingControl()
                if sibling:
                    self.contact_info["group_nickname"] = sibling.Name.strip()
            elif text.startswith("地区："):
                sibling = contactwnd.GetNextSiblingControl()
                if sibling:
                    self.contact_info["area"] = sibling.Name.strip()
            elif text.startswith("备注"):
                sibling = contactwnd.GetNextSiblingControl()
                if sibling and sibling.TextControl().Exists(0):
                    self.contact_info["remark"] = sibling.TextControl().Name.strip()
            elif text.startswith("标签"):
                sibling = contactwnd.GetNextSiblingControl()
                if sibling:
                    self.contact_info["tags"] = sibling.Name.strip()
            elif text.startswith("来源"):
                sibling = contactwnd.GetNextSiblingControl()
                if sibling:
                    self.contact_info["source"] = sibling.Name.strip()
            elif text.startswith("个性签名"):
                sibling = contactwnd.GetNextSiblingControl()
                if sibling:
                    self.contact_info["signature"] = sibling.Name.strip()
            elif text.startswith("共同群聊"):
                sibling = contactwnd.GetNextSiblingControl()
                if sibling:
                    self.contact_info["same_group"] = sibling.Name.strip()
            if self.contact_info['nickname'] is None:
                self.contact_info['nickname'] = self.api.ButtonControl().Name

        for child in contactwnd.GetChildren():
            self._extract_info(child)

    def _choose_menu(self, menu_name):
        more_control = self.api.ButtonControl(Name='更多')
        if not more_control.Exists(0):
            return 
        more_control.Click()
        menu_control = self.api.MenuControl()
        menu_dict = {item.Name: item for item in menu_control.ListControl().GetChildren() if item.Name}
        if menu_name in menu_dict:
            time.sleep(1)
            menu_dict[menu_name].Click(move=True, simulateMove=False)
            return True
        else:
            return
        
    def ModifyRemarkOrTags(self, remark: str=None, tags: list=None):
        if all([not remark, not tags]):
            return False
        if not self._choose_menu("设置备注和标签"):
            wxlog.debug('该用户不支持修改备注和标签')
            return False
        dialogwnd = self.api.WindowControl(ClassName='WeUIDialog')
        if remark:
            edit = dialogwnd.TextControl(Name='备注名').GetParentControl().EditControl()
            edit.Click()
            edit.ShortcutSelectAll()
            SetClipboardText(remark)
            edit.ShortcutPaste(click=False)
        if tags:
            edit_btn = dialogwnd.TextControl(Name='标签').GetParentControl().ButtonControl()
            edit_btn.Click()
            tagwnd = dialogwnd.WindowControl(ClassName='StandardConfirmDialog')
            edit = tagwnd.EditControl(Name="输入标签")
            edit.Click()
            for tag in tags:
                edit.Input(tag)
                edit.SendKeys('{Enter}')
            tagwnd.ButtonControl(Name='确定').Click()
        dialogwnd.ButtonControl(Name='确定').Click()
        return True
        
    def Close(self):
        self.api.SendKeys('{Esc}')

class SessionChatRoomDetailWnd:
    _cls = 'SessionChatRoomDetailWnd'

    def __init__(self, parent):
        self.parent = parent
        self.api = parent.UiaAPI.Control(ClassName=self._cls, searchDepth=1)

    def _edit(self, key, value):
        wxlog.debug(f'修改{key}为`{value}`')
        btn = self.api.TextControl(Name=key).GetParentControl().ButtonControl(Name=key)
        if btn.Exists(0):
            RollIntoView(self.api, btn)
            btn.Click()
        else:
            wxlog.debug(f'当前非群聊，无法修改{key}')
            return False
        while True:
            edit_hwnd_list = [i[0] for i in GetAllWindowExs(self.api.NativeWindowHandle) if i[1] == 'EditWnd']
            if edit_hwnd_list:
                edit_hwnd = edit_hwnd_list[0]
                break
            btn.Click()
        edit_win32 = uia.Win32(edit_hwnd)
        edit_win32.shortcut_select_all()
        edit_win32.send_keys_shortcut('{DELETE}')
        edit_win32.input(value)
        edit_win32.send_keys_shortcut('{ENTER}')
        return True

    def edit_group_name(self, new_name):
        """编辑群聊名称
        
        Args:
            new_name (str): 新的群聊名称
        """
        key = '群聊名称'
        return self._edit(key, new_name)

    def edit_remark(self, remark):
        """编辑群聊备注
        
        Args:
            remark (str): 新的群聊备注
        """
        if self.api.TextControl(Name='仅群主或管理员可以修改').Exists(0):
            wxlog.debug('当前用户无权限修改群聊备注')
            return False
        key = '备注'
        return self._edit(key, remark)

    def edit_my_name(self, my_name):
        """编辑我在本群的昵称
        
        Args:
            my_name (str): 新的昵称
        """
        key = '我在本群的昵称'
        return self._edit(key, my_name)

    def edit_group_notice(self, notice):
        """编辑群公告
        
        Args:
            notice (str | list): 新的群公告
        """
        self.api.TextControl(Name='群公告').GetParentControl().ButtonControl(Name='点击编辑群公告').Click()
        announcementwnd = uia.WindowControl(ClassName='ChatRoomAnnouncementWnd', searchDepth=1)
        if announcementwnd.TextControl(Name="仅群主和管理员可编辑").Exists(0):
            wxlog.debug('当前用户无权限修改群公告')
            announcementwnd.SendKeys('{Esc}')
            return False
        edit_btn_control = announcementwnd.ButtonControl(Name='编辑')
        if edit_btn_control.Exists(0):
            edit_btn_control.Click()
        edit = announcementwnd.EditControl()
        edit.Click()
        edit.ShortcutSelectAll(click=False)
        if isinstance(notice, str):
            # edit.Input(notice)
            SetClipboardText(notice)
            edit.ShortcutPaste(click=False)
        elif isinstance(notice, list) and notice:
            SetClipboardText(notice[0])
            edit.ShortcutPaste(click=False)
            for i in notice[1:]:
                announcementwnd.ButtonControl(Name='分隔线').Click()
                SetClipboardText(i)
                edit.ShortcutPaste(click=False)
        announcementwnd.ButtonControl(Name='完成').Click()
        announcementwnd.PaneControl(ClassName='WeUIDialog').ButtonControl(Name='发布').Click()

    def quit(self):
        """退出群聊"""
        quit_btn = self.api.ButtonControl(Name='退出群聊')
        if quit_btn.Exists(0):
            quit_btn.Click()
        else:
            wxlog.debug('当前非群聊，无法退出')
            return
        RollIntoView(self.api, quit_btn)
        quit_btn.Click()
        dialog = self.parent.UiaAPI.PaneControl(ClassName='WeUIDialog')
        if dialog.TextControl(RegexName='将退出群聊“.*?”').Exists(0):
            dialog.ButtonControl(Name='退出').Click()

    def close(self):
        try:
            self.api.SendKeys('{ESC}')
        except Exception as e:
            pass


class ChatHistoryWnd:
    _clsname = 'FileManagerWnd'

    def __init__(self):
        self.api = uia.WindowControl(ClassName=self._clsname)

    def __repr__(self) -> str:
        return f"<wxauto ChatHistoryWnd Object at {hex(id(self))}>"
    
    def GetHistory(self):
        msgids = []
        msgs = []
        listcontrol = self.api.ListControl()
        while True:
            listitems = listcontrol.GetChildren()
            listitemids = [item.GetRuntimeId() for item in listitems]
            try:
                msgids = msgids[msgids.index(listitemids[0]):]
            except:
                pass
            for item in listitems:
                msgid = item.GetRuntimeId()
                if msgid not in msgids:
                    msgids.append(msgid)
                    msgs.append(parse_msg(item))
            topcontrol = listitems[-1]
            top = topcontrol.BoundingRectangle.top
            self.api.WheelDown(wheelTimes=3)
            time.sleep(0.1)
            if topcontrol.Exists(0.1) and top == topcontrol.BoundingRectangle.top and listitemids == [item.GetRuntimeId() for item in listcontrol.GetChildren()]:
                self.api.SendKeys('{Esc}')
                break
        return msgs