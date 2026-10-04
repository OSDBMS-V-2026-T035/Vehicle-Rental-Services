from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak,
    Table, TableStyle, KeepTogether, Flowable
)
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.colors import HexColor
import os


OUT = os.path.join(os.path.dirname(__file__), 'output', 'pdf', 'computer_networks_units_1_2_exam_notes.pdf')
os.makedirs(os.path.dirname(OUT), exist_ok=True)

NAVY = HexColor('#17324D')
BLUE = HexColor('#1E6A96')
TEAL = HexColor('#0E7490')
PALE = HexColor('#EAF3F7')
PALE2 = HexColor('#F4F7FA')
GOLD = HexColor('#C47E16')
INK = HexColor('#20262B')
MUTED = HexColor('#53616D')
RED = HexColor('#A43D3D')
GREEN = HexColor('#25734D')

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='CoverTitle', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=25, leading=30, textColor=NAVY, alignment=TA_CENTER, spaceAfter=10))
styles.add(ParagraphStyle(name='CoverSub', parent=styles['Normal'], fontName='Helvetica', fontSize=13, leading=18, textColor=MUTED, alignment=TA_CENTER, spaceAfter=8))
styles.add(ParagraphStyle(name='H1x', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=NAVY, spaceBefore=10, spaceAfter=8, keepWithNext=True))
styles.add(ParagraphStyle(name='H2x', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=BLUE, spaceBefore=9, spaceAfter=5, keepWithNext=True))
styles.add(ParagraphStyle(name='H3x', parent=styles['Heading3'], fontName='Helvetica-Bold', fontSize=10.8, leading=13.5, textColor=TEAL, spaceBefore=6, spaceAfter=3, keepWithNext=True))
styles.add(ParagraphStyle(name='Bodyx', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.5, leading=13.2, textColor=INK, spaceAfter=5))
styles.add(ParagraphStyle(name='Smallx', parent=styles['BodyText'], fontName='Helvetica', fontSize=8.2, leading=10.5, textColor=MUTED, spaceAfter=3))
styles.add(ParagraphStyle(name='Exam', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.3, leading=13, textColor=INK, leftIndent=9, firstLineIndent=-9, spaceAfter=4))
styles.add(ParagraphStyle(name='Callout', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=9.3, leading=13, textColor=NAVY, spaceAfter=4))
styles.add(ParagraphStyle(name='Formula', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=10.2, leading=14, textColor=RED, alignment=TA_CENTER, spaceAfter=4))
styles.add(ParagraphStyle(name='TOC', parent=styles['BodyText'], fontName='Helvetica', fontSize=10, leading=15, textColor=INK, leftIndent=8, spaceAfter=2))
styles.add(ParagraphStyle(name='Tbl', parent=styles['BodyText'], fontName='Helvetica', fontSize=8.5, leading=10.5, textColor=INK, spaceAfter=0))
styles.add(ParagraphStyle(name='TblHead', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=8.5, leading=10.5, textColor=colors.white, spaceAfter=0))


def P(text, style='Bodyx'):
    return Paragraph(text, styles[style])


def bullets(items, style='Exam'):
    return [P('- ' + x, style) for x in items]


def callout(title, text, color=PALE):
    t = Table([[P(title, 'Callout')], [P(text, 'Bodyx')]], colWidths=[166*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), color),
        ('BOX', (0, 0), (-1, -1), 0.7, BLUE),
        ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return t


def table(data, widths, header=True, font=8.5):
    converted = []
    for ri, row in enumerate(data):
        prow = []
        for cell in row:
            if isinstance(cell, Flowable):
                prow.append(cell)
            else:
                style = 'TblHead' if header and ri == 0 else 'Tbl'
                prow.append(Paragraph(str(cell).replace('&', '&amp;'), styles[style]))
        converted.append(prow)
    t = Table(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign='LEFT')
    cmds = [
        ('GRID', (0, 0), (-1, -1), 0.35, HexColor('#9AA8B2')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), font),
        ('LEADING', (0, 0), (-1, -1), font + 2),
    ]
    if header:
        cmds += [('BACKGROUND', (0, 0), (-1, 0), NAVY), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold')]
        for r in range(1, len(data)):
            if r % 2 == 0:
                cmds.append(('BACKGROUND', (0, r), (-1, r), PALE2))
    t.setStyle(TableStyle(cmds))
    return t


class Diagram(Flowable):
    def __init__(self, kind, caption='', width=166*mm, height=44*mm):
        Flowable.__init__(self)
        self.kind, self.caption, self.width, self.height = kind, caption, width, height
        self.spaceAfter = 5

    def draw_box(self, c, x, y, w, h, label, fill=PALE, stroke=BLUE, fs=8.3):
        c.setFillColor(fill); c.setStrokeColor(stroke); c.setLineWidth(0.8)
        c.roundRect(x, y, w, h, 4, fill=1, stroke=1)
        c.setFillColor(INK); c.setFont('Helvetica-Bold', fs)
        lines = label.split('\n')
        for i, line in enumerate(lines):
            c.drawCentredString(x+w/2, y+h/2 + (len(lines)-1-i)*5 - 3, line)

    def arrow(self, c, x1, y1, x2, y2, label=None):
        c.setStrokeColor(NAVY); c.setFillColor(NAVY); c.setLineWidth(1)
        c.line(x1, y1, x2, y2)
        import math
        a = math.atan2(y2-y1, x2-x1)
        for d in (2.65, -2.65):
            c.line(x2, y2, x2-6*math.cos(a+d), y2-6*math.sin(a+d))
        if label:
            c.setFont('Helvetica', 7.2); c.drawCentredString((x1+x2)/2, (y1+y2)/2+4, label)

    def draw(self):
        c = self.canv; W = self.width; H = self.height
        c.setFillColor(colors.white); c.setStrokeColor(HexColor('#C7D2D9')); c.roundRect(0, 0, W, H, 5, fill=1, stroke=1)
        if self.kind == 'internet':
            self.draw_box(c, 8, H/2-10, 29, 20, 'Host A')
            self.draw_box(c, W-37, H/2-10, 29, 20, 'Host B')
            self.draw_box(c, 52, H/2-11, 34, 22, 'Access\nnetwork')
            self.draw_box(c, W-86, H/2-11, 34, 22, 'Access\nnetwork')
            self.draw_box(c, W/2-31, H/2-13, 62, 26, 'Internet core\nrouters + links', fill=HexColor('#FFF4DE'), stroke=GOLD)
            self.arrow(c, 37, H/2, 52, H/2); self.arrow(c, 86, H/2, W/2-31, H/2); self.arrow(c, W/2+31, H/2, W-86, H/2); self.arrow(c, W-52, H/2, W-37, H/2)
        elif self.kind == 'switching':
            self.draw_box(c, 10, H-25, 42, 17, 'Message')
            self.draw_box(c, 61, H-25, 42, 17, 'Packet 1')
            self.draw_box(c, 112, H-25, 42, 17, 'Packet 2')
            self.draw_box(c, 10, 8, 42, 17, 'Circuit')
            self.draw_box(c, 61, 8, 42, 17, 'Reserved')
            self.draw_box(c, 112, 8, 42, 17, 'Path')
            c.setFillColor(MUTED); c.setFont('Helvetica-Bold', 8); c.drawString(5, H-7, 'Packet switching'); c.drawString(5, 29, 'Circuit switching')
            self.arrow(c, 52, H-16, 61, H-16); self.arrow(c, 103, H-16, 112, H-16); self.arrow(c, 52, 16, 61, 16); self.arrow(c, 103, 16, 112, 16)
        elif self.kind == 'delay':
            labels = [('Processing', 'check + route'), ('Queueing', 'wait for link'), ('Transmission', 'L / R'), ('Propagation', 'd / s')]
            x = 7
            for i, (a, b) in enumerate(labels):
                self.draw_box(c, x, H/2-12, 35, 24, a+'\n'+b, fill=PALE if i < 2 else HexColor('#FFF4DE'), stroke=BLUE if i < 2 else GOLD, fs=7.1)
                if i < 3: self.arrow(c, x+35, H/2, x+42, H/2)
                x += 42
        elif self.kind == 'layers':
            names = ['Application', 'Transport', 'Network', 'Link', 'Physical']
            x1, x2 = 17, 92
            for i, n in enumerate(names):
                y = H-13-i*9
                self.draw_box(c, x1, y, 56, 7, n, fill=PALE if i != 2 else HexColor('#FFF4DE'), stroke=BLUE, fs=6.8)
                self.draw_box(c, x2, y, 56, 7, n, fill=PALE2, stroke=TEAL, fs=6.8)
            c.setFillColor(MUTED); c.setFont('Helvetica', 7); c.drawCentredString(45, 4, 'sender'); c.drawCentredString(120, 4, 'receiver')
            self.arrow(c, 73, H/2, 92, H/2, 'headers added')
        elif self.kind == 'encap':
            c.setFillColor(INK); c.setFont('Helvetica-Bold', 8); c.drawString(6, H-12, 'Encapsulation at sender')
            items = [('M', 'message'), ('Ht | M', 'segment'), ('Hn | Ht | M', 'datagram'), ('Hl | Hn | Ht | M', 'frame')]
            x = 8
            for i, (a, b) in enumerate(items):
                w = 34 + i*2
                c.setFillColor([PALE, HexColor('#E4F2EE'), HexColor('#FFF4DE'), HexColor('#F3E8F3')][i]); c.setStrokeColor(BLUE); c.roundRect(x, H/2-8, w, 16, 3, fill=1, stroke=1)
                c.setFillColor(INK); c.setFont('Helvetica-Bold', 7.2); c.drawCentredString(x+w/2, H/2+1, a); c.setFont('Helvetica', 6.3); c.drawCentredString(x+w/2, H/2-6, b)
                if i < 3: self.arrow(c, x+w, H/2, x+w+6, H/2)
                x += w + 8
        elif self.kind == 'clientserver':
            self.draw_box(c, 12, H/2-12, 42, 24, 'Client\nprocess')
            self.draw_box(c, W-54, H/2-12, 42, 24, 'Server\nprocess')
            self.draw_box(c, W/2-17, H/2-10, 34, 20, 'Socket', fill=HexColor('#FFF4DE'), stroke=GOLD)
            self.arrow(c, 54, H/2+6, W/2-17, H/2+6, 'request'); self.arrow(c, W/2+17, H/2-6, W-54, H/2-6, 'response')
        elif self.kind == 'http':
            self.draw_box(c, 10, H/2-11, 43, 22, 'Browser')
            self.draw_box(c, W-53, H/2-11, 43, 22, 'Web server')
            self.arrow(c, 53, H/2+6, W-53, H/2+6, 'HTTP request')
            self.arrow(c, W-53, H/2-6, 53, H/2-6, 'HTTP response')
            c.setFillColor(MUTED); c.setFont('Helvetica', 7.2); c.drawCentredString(W/2, 8, 'TCP connection: one object (non-persistent) or many objects (persistent)')
        elif self.kind == 'email':
            xs = [8, 58, 108, 158]
            labs = ['Alice UA', 'Alice mail\nserver', 'Bob mail\nserver', 'Bob UA']
            for x, lab in zip(xs, labs): self.draw_box(c, x, H/2-11, 38, 22, lab, fill=PALE)
            for i in range(3): self.arrow(c, xs[i]+38, H/2+5, xs[i+1], H/2+5, 'SMTP')
            self.arrow(c, 146, H/2-5, 158, H/2-5, 'IMAP/HTTP')
        elif self.kind == 'dns':
            self.draw_box(c, 8, 8, 32, 18, 'Host')
            self.draw_box(c, 52, 8, 42, 18, 'Local DNS')
            self.draw_box(c, 108, H-25, 42, 18, 'Root')
            self.draw_box(c, 108, 8, 42, 18, 'TLD .com')
            self.draw_box(c, 108, H/2-9, 42, 18, 'Auth DNS')
            self.arrow(c, 40, 17, 52, 17); self.arrow(c, 94, 17, 108, H-16); self.arrow(c, 94, 17, 108, H/2); self.arrow(c, 94, 17, 108, 17); self.arrow(c, 150, H-16, 150, H/2+9); self.arrow(c, 150, H/2-9, 150, 17)
            c.setFillColor(MUTED); c.setFont('Helvetica', 7); c.drawString(10, H-10, 'name -> IP address')
        elif self.kind == 'dash':
            self.draw_box(c, 8, H/2-11, 32, 22, 'Video\nserver')
            self.draw_box(c, 63, H/2-13, 42, 26, 'CDN\nchunks', fill=HexColor('#E4F2EE'), stroke=GREEN)
            self.draw_box(c, 128, H/2-11, 32, 22, 'Client\nbuffer')
            self.arrow(c, 40, H/2, 63, H/2, 'manifest'); self.arrow(c, 105, H/2, 128, H/2, 'chunk')
            c.setFillColor(MUTED); c.setFont('Helvetica', 7); c.drawCentredString(84, 8, 'same content encoded at multiple rates')
        elif self.kind == 'windows':
            c.setFillColor(INK); c.setFont('Helvetica-Bold', 8); c.drawString(8, H-12, 'Sliding-window reliability')
            for i in range(8):
                x = 10+i*18; fill = HexColor('#E4F2EE') if i < 4 else HexColor('#F4F7FA')
                c.setFillColor(fill); c.setStrokeColor(TEAL); c.rect(x, H/2-5, 16, 10, fill=1, stroke=1); c.setFillColor(INK); c.setFont('Helvetica', 6.7); c.drawCentredString(x+8, H/2-2, str(i+1))
            c.setFillColor(MUTED); c.setFont('Helvetica', 7); c.drawString(10, 10, 'GBN: error may retransmit the missing packet and all later packets')
            c.drawString(10, 2, 'SR: receiver buffers correct packets and retransmits only the missing packet')
        elif self.kind == 'p2p':
            cx, cy = W/2, H/2
            self.draw_box(c, cx-18, cy-10, 36, 20, 'Peer A', fill=HexColor('#FFF4DE'), stroke=GOLD)
            pts = [(25, H-17), (25, 9), (W-61, H-17), (W-61, 9)]
            for i, (x, y) in enumerate(pts):
                self.draw_box(c, x, y, 36, 17, 'Peer '+chr(66+i), fill=PALE, stroke=BLUE, fs=7.4)
                self.arrow(c, cx-18 if x < cx else cx+18, cy, x+36 if x < cx else x, y+8)
        c.setFillColor(MUTED); c.setFont('Helvetica-Oblique', 7.2); c.drawCentredString(W/2, -8, self.caption)


class CNDoc(BaseDocTemplate):
    def __init__(self, filename):
        BaseDocTemplate.__init__(self, filename, pagesize=A4, leftMargin=22*mm, rightMargin=22*mm, topMargin=18*mm, bottomMargin=17*mm, title='Computer Networks Units 1 and 2 Exam Notes')
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id='normal')
        self.addPageTemplates([PageTemplate(id='main', frames=frame, onPage=self.header_footer)])

    def header_footer(self, c, doc):
        c.saveState()
        if doc.page > 1:
            c.setStrokeColor(HexColor('#D7E0E5')); c.line(self.leftMargin, A4[1]-12*mm, A4[0]-self.rightMargin, A4[1]-12*mm)
            c.setFont('Helvetica-Bold', 7.5); c.setFillColor(NAVY); c.drawString(self.leftMargin, A4[1]-9*mm, 'COMPUTER NETWORKS | UNITS 1 AND 2')
            c.setFont('Helvetica', 7.5); c.setFillColor(MUTED); c.drawRightString(A4[0]-self.rightMargin, A4[1]-9*mm, 'Exam-ready notes')
        c.setStrokeColor(HexColor('#D7E0E5')); c.line(self.leftMargin, 12*mm, A4[0]-self.rightMargin, 12*mm)
        c.setFont('Helvetica', 7.5); c.setFillColor(MUTED); c.drawString(self.leftMargin, 8*mm, 'Prepared from the supplied college PPTs, syllabus image, and 2025 PYQs')
        c.drawRightString(A4[0]-self.rightMargin, 8*mm, 'Page %d' % doc.page)
        c.restoreState()


story = []

# Cover
story += [Spacer(1, 25*mm), P('COMPUTER NETWORKS', 'CoverTitle'), P('Units 1 and 2', 'CoverTitle'), Spacer(1, 5*mm), P('Conceptual notes, diagrams, formulas, and solved previous-year questions', 'CoverSub'), Spacer(1, 10*mm)]
story.append(Table([[P('Designed for university examination writing', 'Callout')], [P('The explanations are intentionally written in complete sentences so that you can reproduce them in a 5-mark or 10-mark answer. Learn the definition, draw the diagram, write the working, then close with the comparison or conclusion.', 'Bodyx')]], colWidths=[145*mm], style=TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),1,BLUE),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)])))
story += [Spacer(1, 18*mm), P('Coverage', 'H2x'), P('Unit 1: Introduction to the Internet, network edge and core, access networks, physical media, switching, ISPs, delay/loss/throughput, security, protocol layering, OSI and TCP/IP.', 'Bodyx'), P('Unit 2: Application architectures, processes and sockets, transport services, HTTP, cookies and caching, e-mail, DNS, P2P, video streaming, DASH, CDNs, and socket programming.', 'Bodyx'), Spacer(1, 18*mm), P('Source note', 'H2x'), P('The supplied PPTs are based on Computer Networking: A Top-Down Approach, 9th edition, by Jim Kurose and Keith Ross. These notes explain the same syllabus in simpler exam language and add worked reasoning where the slides are terse.', 'Smallx'), PageBreak()]

story += [P('How to write a 10-mark answer', 'H1x'), P('Use the following pattern whenever the question asks explain, discuss, compare, or describe:', 'Bodyx')]
story += bullets(['Start with a one or two sentence definition.', 'Draw a labelled diagram. A simple correct diagram earns clarity even when the wording is long.', 'Explain the working in numbered steps, using the vocabulary of the protocol or layer.', 'Add advantages, limitations, formulas, or a comparison table when the question asks for them.', 'End with one short conclusion that connects the mechanism to its purpose.'])
story += [callout('High-value exam habit', 'Do not write only keywords such as reliable, fast, or scalable. Explain what mechanism produces that property. For example, TCP is reliable because it uses sequence numbers, acknowledgements, timers, retransmissions, and checksum-based error detection.', HexColor('#FFF8E8')), P('Course map', 'H2x')]
story.append(table([
    ['Unit', 'Core areas', 'Typical question verbs'],
    ['1', 'Internet basics, edge/core, switching, delay, performance, layers', 'Define, compare, calculate, trace, explain'],
    ['2', 'HTTP, SMTP/IMAP, DNS, P2P, streaming/CDN, sockets', 'Describe, differentiate, trace, justify, illustrate'],
], [14*mm, 94*mm, 58*mm]))
story.append(PageBreak())

# UNIT 1
story += [P('UNIT 1 | INTRODUCTION TO COMPUTER NETWORKS', 'H1x'), P('1.1 The Internet: two useful views', 'H2x'), P('The Internet is a global network of interconnected networks. It connects billions of end systems such as laptops, phones, servers, sensors, and smart devices using communication links and packet switches. Routers and switches forward packets from a source to a destination.', 'Bodyx'), Diagram('internet', 'A simplified view of hosts, access networks, and the Internet core'), P('<b>Nuts-and-bolts view.</b> The Internet contains end systems, communication links, packet switches, routers, switches, and networks operated by different organizations. The links may use copper, fibre, radio, or satellite.', 'Bodyx'), P('<b>Services view.</b> The Internet provides a programming interface to distributed applications. Web browsing, e-mail, video streaming, games, social media, and video calls use transport services supplied by the network. An application sends data to a socket and receives data from a socket.', 'Bodyx'), P('1.2 What is a protocol?', 'H2x'), P('A protocol is a set of rules that defines the format and order of messages exchanged between communicating entities and the actions taken when a message is sent or received. Human conversation also follows protocols, but computer-network protocols must be precise enough for machines to implement.', 'Bodyx')]
story += bullets(['Message syntax: the structure and fields of a message.', 'Message semantics: the meaning of each field.', 'Timing and actions: when a message is sent and what the receiver does next.', 'Examples: HTTP for the Web, SMTP for mail transfer, DNS for name resolution, TCP and IP for transport and network communication.'])
story += [callout('Exam-ready definition', 'A network protocol specifies the format, order, and actions associated with messages exchanged by network entities. It enables independent devices and software implementations to communicate correctly.', PALE), P('1.3 Network edge: hosts, clients, and servers', 'H2x'), P('The network edge contains end systems, also called hosts. A host runs application processes and is the original source or final destination of application data. A client process usually initiates a request. A server process usually waits for requests and provides a service.', 'Bodyx')]
story.append(table([
    ['Term', 'Meaning', 'Example'],
    ['Host / end system', 'A device at the edge of the network that runs applications and sends or receives data.', 'Laptop, smartphone, web server, sensor'],
    ['Client', 'A process that initiates communication to obtain a service.', 'Browser requesting a Web page'],
    ['Server', 'A process that waits for requests and sends a response or service.', 'Apache server returning an HTML file'],
], [33*mm, 86*mm, 47*mm]))
story += [P('A Web server is an end system when it is a physical or virtual host connected to the Internet. The word server can also mean the application process running on that host.', 'Bodyx'), P('1.4 Access networks and physical media', 'H2x'), P('An access network connects an end system to its first router, often called the edge router. The access link determines how the user enters the Internet and often becomes the bottleneck.', 'Bodyx')]
story.append(table([
    ['Access network', 'Working and exam points'],
    ['Cable / HFC', 'Uses a hybrid fibre-coax distribution network. Many homes share the cable segment to a cable headend. Frequency division multiplexing separates data and television channels. It is usually asymmetric, with higher downstream than upstream capacity.'],
    ['DSL', 'Uses the existing telephone line. A DSL modem and DSLAM separate voice and data and connect the subscriber to the central office. The access line is normally dedicated to the subscriber.'],
    ['Home network', 'A modem/router often combines routing, firewall, NAT, wired Ethernet, and Wi-Fi access-point functions.'],
    ['Wi-Fi / cellular', 'A wireless access point or cellular base station connects mobile devices to a router or carrier network. Wi-Fi covers a building-scale area; 4G/5G covers a much larger geographic area.'],
    ['Enterprise / campus', 'Mixes Ethernet switches, Wi-Fi access points, routers, and servers. Data centers use high-bandwidth links to connect many servers.'],
], [34*mm, 132*mm], font=8.2))
story += [P('Physical media', 'H3x'), P('Guided media carry signals through a solid medium. Unguided media carry radio signals through the air. The choice affects rate, distance, interference, cost, and mobility.', 'Bodyx')]
story.append(table([
    ['Medium', 'Main characteristics'],
    ['Twisted pair', 'Two insulated copper wires. Common in Ethernet. Category 5/6 cables support increasingly higher rates over short distances.'],
    ['Coaxial cable', 'Two concentric copper conductors. Supports broadband transmission and multiple frequency channels.'],
    ['Fibre optic', 'Glass fibre carries light pulses. Very high rate, long distance, low error rate, and resistance to electromagnetic noise.'],
    ['Radio', 'No physical wire. Supports Wi-Fi, cellular, Bluetooth, microwave, and satellite. Reflection, obstruction, interference, and propagation conditions affect performance.'],
], [34*mm, 132*mm]))
story.append(PageBreak())

story += [P('UNIT 1 | NETWORK CORE AND SWITCHING', 'H1x'), P('1.5 The network core', 'H2x'), P('The network core is a mesh of interconnected routers. End systems break application messages into packets, and routers forward packets over a path to the destination.', 'Bodyx'), Diagram('switching', 'Packet switching breaks data into packets; circuit switching reserves a path or capacity'), P('<b>Forwarding</b> is the local action of moving an arriving packet from an input link to the correct output link using a forwarding table. <b>Routing</b> is the network-wide process of determining the path from source to destination using routing algorithms.', 'Bodyx'), P('Packet switching', 'H2x'), P('In packet switching, a message is divided into packets. Each packet carries a destination address in its header and may share links with packets from other users. A router normally uses store-and-forward: it receives the complete packet before transmitting it on the next link.', 'Bodyx')]
story += bullets(['Transmission delay for an L-bit packet on an R-bit/s link is L/R seconds.', 'Queueing occurs when packets arrive at an output link faster than the link can transmit them.', 'A finite buffer can overflow. A packet arriving when the buffer is full is dropped, producing packet loss.', 'Packet switching is efficient for bursty traffic because link capacity is shared on demand.', 'Congestion can produce variable delay, loss, and retransmissions.'])
story += [P('Circuit switching', 'H2x'), P('In circuit switching, the network reserves end-to-end resources for a call before data transfer. The reservation may be a frequency band in FDM or periodic time slots in TDM. Once established, the circuit provides predictable service, but reserved capacity is idle when the user has nothing to send.', 'Bodyx')]
story.append(table([
    ['Point', 'Packet switching', 'Circuit switching'],
    ['Resource allocation', 'On demand; shared', 'Reserved for a call'],
    ['Setup', 'Usually no dedicated call setup', 'Call setup is required'],
    ['Performance', 'Delay and loss can vary with congestion', 'More predictable after setup'],
    ['Efficiency', 'Good for bursty data', 'Can waste capacity during silence'],
    ['Typical use', 'Internet data traffic', 'Traditional telephone networks'],
], [33*mm, 61*mm, 72*mm]))
story += [P('FDM and TDM', 'H3x'), P('In Frequency Division Multiplexing, the link spectrum is divided into frequency bands and each call receives a band. In Time Division Multiplexing, time is divided into repeating slots and each call receives one or more slots. TDM allows each user to transmit at the full link rate during the assigned slot, while FDM limits a user to the rate of the allocated band.', 'Bodyx'), P('Three phases of circuit switching', 'H3x')]
story += bullets(['Setup phase: reserve resources along the path and establish the circuit.', 'Data-transfer phase: send data using the reserved circuit.', 'Teardown phase: release the resources after communication ends.'])
story += [callout('Circuit-switching advantage', 'A circuit-switched network offers guaranteed or predictable performance after setup because the resources are dedicated. Its main disadvantages are setup delay, wasted capacity for idle users, and limited flexibility during bursty traffic.', HexColor('#FFF8E8')), P('1.6 Internet structure: a network of networks', 'H2x'), P('Access ISPs connect homes, enterprises, and mobile users. Regional ISPs connect access ISPs. Tier-1 or global transit ISPs provide wide-area connectivity. Internet exchange points allow networks to peer directly. Large content providers such as video and cloud companies may operate private networks and place servers near users.', 'Bodyx')]
story.append(table([
    ['Component', 'Role'],
    ['Access ISP', 'Provides the last-mile connection to homes, campuses, businesses, or mobile users.'],
    ['Regional ISP', 'Aggregates access networks and connects them to larger providers or peers.'],
    ['Tier-1 ISP', 'Large national or international backbone with extensive interconnection.'],
    ['IXP / peering', 'A meeting point where independent networks exchange traffic directly.'],
    ['Content provider network / CDN', 'Private infrastructure that places content and services close to end users.'],
], [51*mm, 115*mm]))
story += [P('For a small business, a Tier-2 or regional ISP is usually the sensible choice: it can provide reliable business access and support at lower cost than a Tier-1 backbone. A Tier-1 connection is justified only when the organization itself needs large-scale backbone reach or transit service.', 'Bodyx'), PageBreak()]

# Unit 1 performance
story += [P('UNIT 1 | DELAY, LOSS, AND THROUGHPUT', 'H1x'), P('1.7 Four components of nodal delay', 'H2x'), P('When a packet travels through a router, its nodal delay is the sum of processing, queueing, transmission, and propagation delay.', 'Bodyx'), Diagram('delay', 'Four delay components at a link'), P('d_nodal = d_proc + d_queue + d_trans + d_prop', 'Formula')]
story.append(table([
    ['Component', 'Meaning', 'Formula / behaviour'],
    ['Processing delay', 'Time to examine the header, check errors, and select the output link.', 'Usually small and approximately constant for a given device.'],
    ['Queueing delay', 'Time waiting in the output buffer before transmission begins.', 'Variable; grows with traffic intensity and congestion.'],
    ['Transmission delay', 'Time to push all L bits into the link.', 'd_trans = L / R'],
    ['Propagation delay', 'Time for a bit to travel through the physical medium.', 'd_prop = d / s'],
], [34*mm, 74*mm, 58*mm]))
story += [P('Transmission and propagation are different. A high-bandwidth link reduces transmission delay, while a shorter physical distance or faster medium reduces propagation delay. Increasing bandwidth does not automatically reduce propagation delay.', 'Bodyx'), P('Queueing and loss', 'H2x'), P('Let a be the average packet arrival rate, L the average packet length, and R the link rate. The traffic intensity is La/R. When this value is close to zero, queueing is small. As it approaches 1, queueing becomes large. If the input rate stays above the service rate, the buffer can fill and packets are dropped.', 'Bodyx'), P('Packet loss can be handled by retransmission from the previous router or source, or it may be left to the application. TCP uses retransmission and congestion control; UDP itself does not provide them.', 'Bodyx'), P('Throughput', 'H2x'), P('Throughput is the rate at which bits are delivered from a sender to a receiver. The end-to-end throughput is limited by the bottleneck link, the slowest effective rate on the path.', 'Bodyx'), P('Throughput = min(sender rate, receiver access rate, bottleneck capacity)', 'Formula')]
story += bullets(['Instantaneous throughput is measured at a particular time.', 'Average throughput is measured over a longer interval.', 'If a server can send at R_s and the client link can receive at R_c, the ideal throughput is min(R_s, R_c).', 'If ten connections share a backbone link fairly, each may receive approximately R/10, subject to other bottlenecks.'])
story += [P('Worked numerical example', 'H2x'), P('A 1500-byte packet (12000 bits) travels from Host A to Host B over one link. The rate is 10 Mbps, distance is 1000 km, propagation speed is 2 x 10^8 m/s, queueing delay is 2 ms, and processing delay is 1 ms.', 'Bodyx'), P('Transmission = 12000 / 10,000,000 = 1.2 ms', 'Formula'), P('Propagation = 1,000,000 / (2 x 10^8) = 5 ms', 'Formula'), P('End-to-end delay = 1.2 + 5 + 2 + 1 = 9.2 ms', 'Formula'), P('In an exam, show the unit conversion from kilometres to metres and from bits per second to the numeric link rate.', 'Bodyx'), P('1.8 Traceroute idea', 'H2x'), P('Traceroute estimates the delay to each router on a path. It sends probes with increasing time-to-live values. The router whose TTL expires returns a response, and the sender measures the round-trip time. A star can mean the probe was lost or the router did not reply.', 'Bodyx')]

# Security and layers
story += [P('UNIT 1 | SECURITY, LAYERS, AND ENCAPSULATION', 'H1x'), P('1.9 Basic network security threats', 'H2x')]
story.append(table([
    ['Threat', 'Meaning', 'Defence idea'],
    ['Packet sniffing', 'A device on a shared medium reads packets that pass by, possibly exposing passwords or data.', 'Encryption, secure protocols, and switched or protected links.'],
    ['IP spoofing', 'An attacker injects a packet with a false source address.', 'Authentication, filtering, and secure protocol checks.'],
    ['Denial of Service', 'Attackers overwhelm a server, link, or service with bogus traffic so legitimate users cannot use it.', 'Firewalls, filtering, rate limiting, monitoring, and distributed defence.'],
], [31*mm, 78*mm, 57*mm]))
story += bullets(['Authentication proves who a communicating party is.', 'Confidentiality prevents outsiders from reading data, usually through encryption.', 'Integrity detects unauthorised modification, for example with message authentication or digital signatures.', 'Access control restricts senders, receivers, applications, or ports. A firewall is a specialised middlebox that filters traffic.'])
story += [P('1.10 Why protocol layering?', 'H2x'), P('Networking is a complex system containing applications, protocols, software, hosts, routers, links, and media. Layering divides the system into modules. Each layer offers a service to the layer above and uses a service from the layer below.', 'Bodyx'), Diagram('layers', 'A simplified TCP/IP stack at two end systems'), P('Advantages of layering', 'H3x')]
story += bullets(['Modularity: one layer can be designed and tested separately.', 'Maintenance: changes inside one layer can remain hidden from other layers.', 'Standardisation: different vendors can implement the same layer interface.', 'Troubleshooting: the location of a problem can be narrowed to a layer.', 'Trade-off: strict layering can add overhead or duplicate functions.'])
story += [P('OSI reference model', 'H2x')]
story.append(table([
    ['OSI layer', 'Main responsibility', 'Examples / note'],
    ['Application', 'Network applications and application protocols.', 'HTTP, SMTP, DNS'],
    ['Presentation', 'Data representation, translation, compression, encryption.', 'Often implemented inside applications in the Internet stack.'],
    ['Session', 'Dialog control, synchronisation, checkpoints, recovery.', 'Often implemented inside applications.'],
    ['Transport', 'Process-to-process delivery, reliability, flow and congestion control.', 'TCP, UDP'],
    ['Network', 'Host-to-host delivery and routing of packets.', 'IP, routing protocols'],
    ['Data link', 'Frame delivery between neighbouring network elements.', 'Ethernet, Wi-Fi, PPP'],
    ['Physical', 'Transmission of raw bits over the medium.', 'Copper, fibre, radio'],
], [34*mm, 75*mm, 57*mm]))
story += [P('TCP/IP Internet stack', 'H2x'), P('The practical Internet stack normally uses application, transport, network, link, and physical layers. The OSI presentation and session functions are usually implemented inside the application layer rather than as separate Internet layers.', 'Bodyx'), P('1.11 Encapsulation', 'H2x'), P('At the sender, each lower layer adds its own header to the data from the layer above. At the receiver, the headers are removed in reverse order. The names are message at the application layer, segment at transport, datagram at network, and frame at link.', 'Bodyx'), Diagram('encap', 'Encapsulation adds a header at each lower layer'), P('Example: if an application message is M, the transport layer forms [H_t | M], the network layer forms [H_n | H_t | M], and the link layer forms [H_l | H_n | H_t | M]. Routers normally remove and add link-layer frames at each hop, while the transport and application data remain end-to-end.', 'Bodyx'), PageBreak()]

story += [P('UNIT 1 | HISTORY AND QUICK REVISION', 'H1x'), P('1.12 Short Internet history', 'H2x')]
story.append(table([
    ['Period', 'Milestone and importance'],
    ['1961-1972', 'Queueing theory and early packet-switching ideas; ARPANET conceived and first nodes operated; early host-to-host protocols and e-mail.'],
    ['1972-1980', 'Internetworking principles, Ethernet, and the growth of independent networks.'],
    ['1980-1990', 'TCP/IP deployment, DNS, SMTP, FTP, congestion control, and new national networks.'],
    ['1990s-2000s', 'ARPANET retired; commercial Web, HTML, HTTP, browsers, search, messaging, and P2P applications expanded.'],
    ['2005-present', 'Broadband, Wi-Fi/4G/5G, cloud services, software-defined networking, content-provider networks, and large-scale mobile use.'],
], [36*mm, 130*mm]))
story += [P('Unit 1 formula sheet', 'H2x')]
story.append(table([
    ['Quantity', 'Formula'],
    ['Transmission delay', 'd_trans = L / R'],
    ['Propagation delay', 'd_prop = d / s'],
    ['Nodal delay', 'd_nodal = d_proc + d_queue + d_trans + d_prop'],
    ['Traffic intensity', 'La / R'],
    ['End-to-end throughput', 'approximately the minimum rate on the path'],
    ['Full mesh pair circuits', 'n(n - 1) / 2'],
], [56*mm, 110*mm]))
story += [callout('Unit 1 last-minute checklist', 'Know host versus end system; packet versus circuit switching; FDM versus TDM; forwarding versus routing; four delay components; throughput bottleneck; security threats; OSI/TCP-IP mapping; and encapsulation.', HexColor('#EAF7EF')), PageBreak()]

# UNIT 2
story += [P('UNIT 2 | APPLICATION LAYER', 'H1x'), P('2.1 Principles of network applications', 'H2x'), P('A network application is a program that runs on end systems and communicates with another program over the network. Developers normally do not write application code inside routers. This separation allows rapid application development at the network edge.', 'Bodyx'), P('Client-server architecture', 'H2x'), P('A server is often always on, has a stable or well-known address, and may run in a data center. Clients contact the server and may be intermittently connected with changing addresses. HTTP, FTP, and traditional mail access are examples.', 'Bodyx'), P('Peer-to-peer architecture', 'H2x'), P('In P2P, end systems communicate directly. A peer can request data from other peers and upload data to them. There is no requirement for one always-on central server. New peers add both demand and upload capacity, giving P2P self-scalability, but peer discovery, security, availability, and management are more difficult.', 'Bodyx'), Diagram('clientserver', 'A client and server communicate through sockets'), Diagram('p2p', 'A P2P swarm: peers both request and provide data'), P('Processes and sockets', 'H2x'), P('A process is a running program. Processes on different hosts exchange messages. A socket is the interface between an application process and the transport layer. It is like a door: the application controls one side, while the operating system and transport protocol deliver data on the other side.', 'Bodyx'), P('An IP address identifies a host, not a unique process. A process is identified by the combination of IP address and port number. Common examples are HTTP port 80, HTTPS port 443, and SMTP port 25.', 'Bodyx'), P('An application-layer protocol defines message types, syntax, semantics, and rules for sending and responding. Open protocols are published in RFCs. Proprietary protocols are controlled by a company or product.', 'Bodyx'), PageBreak()]

story += [P('UNIT 2 | TRANSPORT SERVICES FOR APPLICATIONS', 'H1x'), P('2.2 What an application needs from transport', 'H2x')]
story.append(table([
    ['Requirement', 'Meaning', 'Examples'],
    ['Reliability / data integrity', 'Data should arrive correctly and completely.', 'File transfer, e-mail, Web transactions'],
    ['Timing', 'Delay should be small enough for the application to remain effective.', 'Interactive games, voice, live video'],
    ['Throughput', 'The application needs a minimum or useful data rate.', 'Video streaming, multimedia'],
    ['Security', 'The application may need confidentiality, authentication, and integrity.', 'Payments, login, private messages'],
], [39*mm, 75*mm, 52*mm]))
story += [P('TCP and UDP', 'H2x')]
story.append(table([
    ['Feature', 'TCP', 'UDP'],
    ['Data transfer', 'Reliable byte stream, in order', 'Unreliable datagrams; loss or reordering may occur'],
    ['Connection', 'Connection-oriented; setup required', 'Connectionless; no handshake before sending'],
    ['Control', 'Flow control and congestion control', 'No built-in flow or congestion control'],
    ['Guarantees', 'No timing or minimum-throughput guarantee', 'No reliability, timing, throughput, or security guarantee'],
    ['Use', 'HTTP, SMTP, IMAP, file transfer', 'DNS queries, streaming or real-time apps when chosen, games, custom apps'],
], [31*mm, 68*mm, 67*mm]))
story += [P('TCP is reliable because it uses checksum, sequence numbers, acknowledgements, timers, retransmissions, and ordered delivery. UDP is useful when an application wants low overhead, message boundaries, fast startup, or direct control of loss and timing. UDP itself does not make an application secure; TLS or another security layer is needed.', 'Bodyx'), P('TLS', 'H2x'), P('A normal TCP or UDP socket carries cleartext unless the application adds security. TLS provides encrypted communication, data integrity, and endpoint authentication. HTTPS is HTTP carried over a secure TLS connection, commonly over TCP; HTTP/3 uses QUIC, which integrates security and transport functions over UDP.', 'Bodyx'), P('2.3 Why HTTP, SMTP, and IMAP use TCP', 'H2x'), P('These protocols transfer Web objects or e-mail where loss, duplication, or reordering would corrupt the application data. TCP supplies reliable in-order delivery, retransmission, flow control, and congestion control. The application therefore does not need to implement those functions itself.', 'Bodyx'), PageBreak()]

# HTTP
story += [P('UNIT 2 | WEB AND HTTP', 'H1x'), P('2.4 Web pages, URLs, and HTTP', 'H2x'), P('A Web page consists of a base HTML file and referenced objects such as images, style sheets, scripts, and video. Each object has a URL containing a host name and a path. HTTP is the application-layer protocol used by a browser and Web server to request and transfer these objects.', 'Bodyx'), Diagram('http', 'HTTP request and response over a TCP connection'), P('HTTP is stateless: the server does not automatically retain information about earlier requests. Statelessness simplifies server recovery and scaling, but applications often add state through cookies, databases, or sessions.', 'Bodyx'), P('Non-persistent and persistent HTTP', 'H2x')]
story.append(table([
    ['Property', 'Non-persistent HTTP', 'Persistent HTTP'],
    ['TCP use', 'A new TCP connection for each object', 'One connection can carry multiple objects'],
    ['Per-object delay', 'Approximately 2 RTT + object transmission time', 'Later objects avoid repeated connection setup'],
    ['Cost', 'More handshakes and operating-system overhead', 'Lower overhead and better performance'],
    ['Typical exam point', 'A page with base HTML plus 10 images may need 11 connections if fetched sequentially.', 'HTTP/1.1 keep-alive allows reuse; browsers may still use concurrency.'],
], [34*mm, 65*mm, 67*mm]))
story += [P('Non-persistent HTTP working', 'H2x')]
story += bullets(['The user enters a URL. The client resolves the host name and opens a TCP connection to the server, usually port 80 for HTTP.', 'The browser sends a GET request containing the path.', 'The server sends an HTTP response containing the object and closes the TCP connection.', 'The browser parses the HTML. For each referenced object, it repeats the connection, request, response, and close sequence.', 'For one object, response time is approximately 2 RTT plus the file transmission time: one RTT to establish TCP and one RTT for the request and first response bytes.'])
story += [P('HTTP request format', 'H2x'), P('A request contains a request line, header lines, a blank line, and an optional entity body. Example:', 'Bodyx'), P('GET /index.html HTTP/1.1<br/>Host: www.example.com<br/>Connection: keep-alive<br/>Accept: text/html<br/><br/>', 'Smallx'), P('Common methods: GET retrieves an object; POST sends form data in the body; HEAD requests only the headers; PUT uploads or replaces an object at a URL.', 'Bodyx'), P('HTTP response format and status codes', 'H2x')]
story.append(table([
    ['Code', 'Meaning'],
    ['200 OK', 'Request succeeded; the object may follow.'],
    ['301 Moved Permanently', 'The new location is supplied in a Location header.'],
    ['304 Not Modified', 'The cached copy is still valid; no object body is sent.'],
    ['400 Bad Request', 'The server cannot understand the request.'],
    ['404 Not Found', 'The requested resource does not exist at the server.'],
    ['505 HTTP Version Not Supported', 'The server does not support the requested HTTP version.'],
], [40*mm, 126*mm]))
story += [P('UNIT 2 | COOKIES, CACHES, AND HTTP EVOLUTION', 'H1x'), P('2.5 Cookies and state', 'H2x'), P('Cookies add state to a stateless HTTP exchange. A site sends a Set-Cookie header in a response. The browser stores the value and sends it in a Cookie header on later requests to the same site. The site can use the identifier to find session data in a backend database.', 'Bodyx')]
story += bullets(['Cookie response header: Set-Cookie: 1678', 'Cookie request header: Cookie: 1678', 'Browser cookie file stores the value.', 'The Web site database stores the associated account, cart, or session state.'])
story += [P('Uses include login sessions, shopping carts, authorisation, and personalised recommendations. First-party cookies come from the site the user visits. Third-party cookies come from an embedded tracker or advertisement and can correlate browsing across sites, creating privacy concerns.', 'Bodyx'), P('2.6 Web caches / proxy servers', 'H2x'), P('A Web cache is both a server to the browser and a client to the origin server. The browser sends a request to the cache. If the object is present and fresh, the cache returns it immediately. Otherwise, the cache requests the object from the origin server, stores a copy, and returns it to the browser.', 'Bodyx')]
story += bullets(['The cache is closer to the client, reducing response time.', 'It reduces traffic on the institution access link and the origin path.', 'It helps a smaller content provider serve many users.', 'The cache must respect freshness and cache-control information.'])
story += [P('Conditional GET', 'H2x'), P('A browser can ask whether its cached copy is still current by sending If-Modified-Since. If the object has not changed, the server sends 304 Not Modified and no object body. If it has changed, the server sends 200 OK and the new object.', 'Bodyx'), P('2.7 HTTP/2 and HTTP/3', 'H2x'), P('HTTP/1.1 pipelining can suffer head-of-line blocking: a small object waits behind a large earlier response. HTTP/2 divides objects into frames and interleaves frame transmission. The server can schedule frames using priorities and may push useful objects. This reduces application-level blocking, although TCP loss recovery can still stall all streams sharing the connection.', 'Bodyx'), P('HTTP/3 uses QUIC over UDP. QUIC provides encrypted connections, reliability, congestion control, and independent stream handling in one transport design. A normal TCP plus TLS design performs two serial handshakes; QUIC can establish the needed state in one RTT and may support 0-RTT resumption.', 'Bodyx')]

# E-mail and DNS
story += [P('UNIT 2 | E-MAIL: SMTP AND IMAP', 'H1x'), P('2.8 E-mail system components', 'H2x'), P('The three main components are the user agent, mail servers, and SMTP. A user agent allows a person to compose, send, and read messages. A mail server contains the user mailbox and an outgoing message queue. SMTP transfers messages between mail servers.', 'Bodyx'), Diagram('email', 'Mail submission, server-to-server SMTP, and recipient retrieval'), P('SMTP uses TCP port 25 and a command-response exchange. It has a greeting or handshake, message transfer, and closure. SMTP commands and responses are ASCII and a message ends with a special CRLF.CRLF sequence.', 'Bodyx'), P('Alice sends mail to Bob', 'H2x')]
story += bullets(['Alice composes a message in her user agent addressed to bob@example.edu.', 'The user agent submits the message to Alice mail server, which places it in the outgoing queue.', 'Alice mail server acts as an SMTP client and opens a TCP connection to Bob mail server.', 'The two servers exchange HELO or EHLO, MAIL FROM, RCPT TO, DATA, and QUIT commands and responses.', 'Bob mail server stores the message in Bob mailbox.', 'Bob retrieves it using IMAP or a Web-mail interface over HTTP/HTTPS.'])
story += [P('SMTP versus e-mail message format', 'H2x'), P('SMTP is the protocol for transferring a message. The message itself has header fields such as To, From, and Subject, followed by a blank line and the body. MAIL FROM and RCPT TO are SMTP commands and should not be confused with the To and From header fields inside the message.', 'Bodyx'), P('IMAP keeps messages on the mail server and supports retrieval, folders, deletion, and synchronisation. Web mail uses HTTP/HTTPS at the browser interface and uses SMTP for sending plus IMAP or a similar access service for retrieving mail.', 'Bodyx'), P('2.9 DNS: Domain Name System', 'H2x'), P('DNS maps human-readable host names to IP addresses. It is a distributed hierarchical database and an application-layer protocol. It also supports host aliasing, mail-server aliasing, and load distribution through multiple addresses.', 'Bodyx'), Diagram('dns', 'A simplified DNS hierarchy and name-resolution path')]
story += [P('Why DNS is distributed', 'H3x')]
story += bullets(['A single central server would be a single point of failure.', 'A central database would receive an enormous query volume.', 'A distant central server would increase response time.', 'A central database would be difficult to maintain for millions of organisations.'])
story += [P('DNS hierarchy', 'H2x'), P('Root name servers direct queries to the correct top-level domain server. TLD servers handle domains such as .com, .org, .edu, and country-code domains. Authoritative name servers are responsible for the records of a particular organisation or domain. A local DNS server serves the client and may answer from its cache or contact the hierarchy.', 'Bodyx'), P('Iterative versus recursive queries', 'H2x')]
story.append(table([
    ['Query type', 'Working', 'Advantage / limitation'],
    ['Iterative', 'Each server returns the name of the next server to contact. The local resolver does the next query itself.', 'Distributes work and gives the resolver control, but requires several exchanges.'],
    ['Recursive', 'The contacted server takes responsibility for resolving the complete name and returns the final answer.', 'Simple for the requester, but places more load on the contacted server and upper hierarchy.'],
], [31*mm, 83*mm, 52*mm]))
story += [P('Without caching, resolving www.example.com normally follows: client to local DNS; local DNS to root; root to .com TLD; TLD to example.com authoritative DNS; authoritative DNS returns the A record; the local DNS returns the IP to the client. With caching, an earlier answer or TLD record may remove some steps.', 'Bodyx')]

story += [P('UNIT 2 | DNS RECORDS, P2P, VIDEO, AND CDNs', 'H1x'), P('DNS caching and records', 'H2x'), P('A DNS server caches a name-to-address mapping after learning it. The time-to-live (TTL) controls how long the entry remains. Caching reduces delay and query traffic, but a cached value can be temporarily stale after a host changes its address.', 'Bodyx')]
story.append(table([
    ['Record', 'Meaning'],
    ['A', 'Maps a host name to an IPv4 address.'],
    ['AAAA', 'Maps a host name to an IPv6 address.'],
    ['NS', 'Identifies the authoritative name server for a domain.'],
    ['CNAME', 'Maps an alias to a canonical host name.'],
    ['MX', 'Identifies the mail server for a domain.'],
], [38*mm, 128*mm]))
story += [P('DNS message format', 'H2x'), P('A DNS query and reply use the same general format: a header, question section, answer records, authority records, and additional records. The header has an identification number, flags, and counts for the sections. A reply may include the answer, information about the authority, and helpful additional records.', 'Bodyx'), P('DNS security issues', 'H3x'), P('DDoS attacks can target root or TLD servers. Attackers can also spoof DNS replies or poison a cache with a false mapping. DNSSEC adds authentication and integrity protection for DNS data.', 'Bodyx'), P('2.10 P2P file sharing and BitTorrent', 'H2x'), P('BitTorrent divides a file into fixed-size pieces. A group of peers sharing the same file is a swarm. A peer downloads pieces from multiple peers while uploading pieces it already has to others.', 'Bodyx')]
story += bullets(['A tracker or distributed peer-discovery mechanism helps a new peer find members of the swarm.', 'A peer with no pieces asks for pieces from several neighbours. It can begin sharing a piece as soon as it obtains and verifies it.', 'Rarest-first selection requests pieces that are least common among neighbours, improving piece diversity and reducing the risk that a rare piece disappears.', 'Tit-for-tat or choking gives upload preference to peers that upload at a useful rate. Optimistic unchoking periodically tests another peer so a new or fast peer can be discovered.', 'A peer that obtains all pieces becomes a seed and continues uploading, improving availability.', 'P2P is self-scalable because every new peer adds demand but can also add upload capacity.'])
story += [P('A client with no data should therefore contact the tracker or peer-discovery service, establish connections with several peers, request rare or available pieces, verify each piece, upload received pieces to earn service, and eventually seed the complete file.', 'Bodyx'), P('2.11 Video streaming', 'H2x'), P('Video is a sequence of images displayed at a constant rate. Compression reduces bits by exploiting spatial redundancy within one frame and temporal redundancy between consecutive frames. CBR uses a fixed encoding rate; VBR changes its rate with scene complexity.', 'Bodyx'), P('The main challenge is continuous playout: the client must display content at the original timing even though network delay and available bandwidth vary. A client-side buffer absorbs jitter. If the buffer empties, playback stalls; if it overflows, capacity is wasted.', 'Bodyx'), Diagram('dash', 'DASH selects encoded chunks and uses buffering to absorb rate changes')]

story += [P('DASH and content distribution networks', 'H1x'), P('2.12 DASH: Dynamic Adaptive Streaming over HTTP', 'H2x'), P('In DASH, the server divides a video into chunks and stores each chunk at several encoding rates. A manifest file lists the URLs and available rates. The client periodically estimates available bandwidth and requests one chunk at a time at the highest sustainable quality.', 'Bodyx')]
story += bullets(['The client decides when to request the next chunk.', 'The client selects a rate based on measured bandwidth and buffer level.', 'The client can request chunks from different servers or CDN nodes.', 'The client lowers the rate when bandwidth falls and raises it when conditions improve.', 'DASH uses ordinary HTTP infrastructure, which works well with caches, proxies, and firewalls.'])
story += [P('2.13 Content distribution networks', 'H2x'), P('A single very large video server creates a single point of failure, a congestion point, and long paths to distant users. A CDN stores copies at geographically distributed nodes and directs users to a nearby or lightly loaded copy.', 'Bodyx'), P('A CDN may use an enter-deep design with many servers inside access networks or a bring-home design with fewer large clusters near access networks. DNS, URL redirection, or an application manifest can direct a user to the selected CDN node.', 'Bodyx'), P('A typical CDN access sequence is: the user receives a video URL, DNS maps the service name or alias to a CDN name, the CDN returns a nearby server address, and the client requests DASH chunks from that server.', 'Bodyx'), P('OTT means over-the-top service: the application provider delivers content over the general Internet rather than operating the access ISP. It must choose what content to place at each node, which node should serve a user, and what rate the client can sustain.', 'Bodyx'), PageBreak()]

# Sockets
story += [P('UNIT 2 | SOCKET PROGRAMMING', 'H1x'), P('2.14 UDP sockets', 'H2x'), P('UDP provides an unreliable datagram service. There is no connection setup. The sender attaches the destination IP address and port to every datagram. The receiver obtains the sender address and port with the received data. Datagrams may be lost or arrive out of order.', 'Bodyx')]
story += bullets(['Client creates a UDP socket.', 'Client sends a datagram to server IP and port.', 'Server receives the datagram and learns the client address.', 'Server processes the message and sends a reply to that address.', 'Client receives the reply and closes the socket.'])
story += [P('UDP pseudo-code', 'H3x'), P('Client: create SOCK_DGRAM socket -> read input -> sendto(server address, port) -> recvfrom() -> display reply -> close. Server: create SOCK_DGRAM socket -> bind to a port -> loop over recvfrom() -> process data -> sendto(client address) .', 'Bodyx'), P('2.15 TCP sockets', 'H2x'), P('TCP provides a reliable, in-order byte stream. The client must contact a server that is already listening. The server has a welcoming socket and creates a new connected socket for each client, so one server can communicate with many clients.', 'Bodyx')]
story += bullets(['Server creates a TCP socket, binds it to a port, and calls listen().', 'Server calls accept() and waits for a connection request.', 'Client creates a TCP socket and calls connect(server IP, port).', 'TCP establishes the connection. The server returns a new connection socket.', 'Client and server exchange bytes using send and recv.', 'The connected socket closes after the exchange; the welcoming socket can continue accepting clients.'])
story += [P('UDP versus TCP socket interaction', 'H2x'), P('UDP is message-oriented and every send includes a destination. TCP is connection-oriented and the connection identifies the peer after setup. TCP preserves order and reliability but adds setup and control overhead. UDP is simpler and faster to start, but the application must tolerate or handle loss, ordering, and timing itself.', 'Bodyx'), P('Timeouts', 'H2x'), P('A socket timeout prevents a program from waiting forever for a reply. The program sets a timeout, performs a blocking receive inside a try block, and handles the timeout exception in an except block. Timeouts are useful for retransmission, failure detection, and servers that should stop serving a silent client.', 'Bodyx'), PageBreak()]

# PYQs
story += [P('SOLVED PREVIOUS-YEAR QUESTIONS', 'H1x'), P('The following answers are based on the supplied 2025 Computer Networks and 2025 Special Paper question sheets. In the exam, draw the small diagram shown in the relevant notes section and then write the numbered explanation.', 'Bodyx'), P('PYQ 1 | Host, end system, and Web server', 'H2x'), P('<b>Answer.</b> A host is a network-connected device that has an address and can send or receive data. An end system is a host at the network edge that runs application programs. Therefore, in the Internet context, host and end system are often used interchangeably, although host emphasises the device and end system emphasises its role as a source or destination of application data.', 'Exam')]
story += bullets(['Examples include laptops, smartphones, tablets, Web servers, mail servers, cloud servers, sensors, cameras, and smart appliances.', 'A client process initiates a request, while a server process waits for requests and provides a service.', 'A Web server is an end system when it is a connected host running Web-server software such as Apache or another HTTP server.', 'Routers and switches are network-core devices. They forward packets but normally do not run the user application that creates the message.'])
story += [P('Conclusion: a Web server is both a host/end system and a server process or service, depending on whether the question refers to hardware or software.', 'Exam'), P('PYQ 2 | Circuit switching versus packet switching; TDM versus FDM', 'H2x'), P('<b>Answer.</b> Circuit switching reserves resources for a complete call, so it provides predictable performance after setup and avoids queueing among calls using separate reserved resources. Packet switching shares resources on demand, so it is efficient for bursty traffic but may experience queueing, variable delay, and packet loss during congestion.', 'Exam')]
story.append(table([
    ['Circuit switching', 'Packet switching'],
    ['Dedicated capacity and predictable service after setup.', 'Capacity shared dynamically among packets.'],
    ['Can waste capacity when the user is silent.', 'Efficient for bursty and intermittent traffic.'],
    ['Requires setup and teardown.', 'Usually no circuit setup; packets carry addresses.'],
    ['Traditional telephone network.', 'Internet data network.'],
], [82*mm, 84*mm]))
story += [P('In FDM, each call gets a separate frequency band for the duration of the call. In TDM, time is divided into repeating slots and each call gets one or more slots. TDM can use the full link rate during its assigned slot, while FDM limits the call to the allocated band. TDM is often easier to allocate digitally and avoids frequency guard-band issues, but it requires synchronised time slots.', 'Exam'), P('PYQ 3 | Three phases and delays in circuit/packet switching', 'H2x'), P('<b>Answer.</b> Circuit switching has setup, data transfer, and teardown phases. Setup reserves resources along the path. Data transfer uses the established circuit. Teardown releases the resources.', 'Exam'), P('Circuit switching has predictable delay and no packet loss caused by competing calls after reservation, but it has setup delay, can waste idle capacity, and is less efficient for bursty data. Packet switching has efficient sharing and no dedicated setup, but it can produce processing, queueing, transmission, and propagation delay. Queue overflow causes loss and retransmissions can increase delay.', 'Exam'), P('PYQ 4 | End-to-end delay components', 'H2x'), P('<b>Answer.</b> For a fixed route, the end-to-end delay is the sum of the delay components at every hop plus any end-system processing:', 'Exam'), P('d_end-to-end = sum(d_proc + d_queue + d_trans + d_prop) over all links and routers', 'Formula'), P('Processing delay, transmission delay, and propagation delay are usually approximately constant for a fixed route and fixed packet/link conditions. Queueing delay is variable because it depends on traffic. Processing can also vary slightly with router load, but queueing is the main variable component.', 'Exam'), P('PYQ 5 | Numerical delay: 1500 bytes over 10 Mbps', 'H2x'), P('<b>Given:</b> L = 1500 bytes = 12000 bits, R = 10,000,000 bits/s, d = 1000 km = 1,000,000 m, s = 2 x 10^8 m/s, queueing = 2 ms, processing = 1 ms.', 'Exam'), P('Transmission = L/R = 12000/10,000,000 = 0.0012 s = 1.2 ms', 'Formula'), P('Propagation = d/s = 1,000,000/(2 x 10^8) = 0.005 s = 5 ms', 'Formula'), P('Total = 1.2 + 5 + 2 + 1 = 9.2 ms', 'Formula')]

story += [P('PYQ 6 | Head-of-line blocking in HTTP/1.1 and HTTP/2', 'H2x'), P('<b>Answer.</b> In HTTP/1.1 pipelining, the server sends responses in request order. If the first requested object is large or its data is delayed, smaller objects behind it wait even when they are ready. This is head-of-line blocking.', 'Exam')]
story += bullets(['HTTP/2 divides objects into frames.', 'The server interleaves frames from different objects and can use priorities.', 'Small objects can finish before a large object, reducing application-level waiting.', 'HTTP/2 still runs over one TCP connection, so loss of a TCP segment can stall all streams until TCP recovers it.', 'HTTP/3 uses QUIC over UDP to reduce cross-stream blocking and combine transport security with the connection.'])
story += [P('PYQ 7 | Web caching: all objects or some objects?', 'H2x'), P('<b>Answer.</b> A browser sends a request to a Web cache. If the object is cached and fresh, the cache returns it. Otherwise it retrieves the object from the origin server, stores a copy if allowed, and returns it to the browser. The cache reduces delay because it is close to the user and reduces traffic on the access link.', 'Exam'), P('Caching does not reduce delay for every object. It helps only for cacheable objects that are already present and fresh, producing a cache hit. A cache miss still requires the origin-server path. Dynamic, private, no-store, or expired objects may not be served from the cache. Therefore, only the hit fraction benefits immediately. Conditional GET can validate a cached object without retransmitting its body.', 'Exam'), P('PYQ 8 | P2P architecture and client/server terminology', 'H2x'), P('<b>Answer.</b> P2P is a distributed architecture in which end systems communicate directly. A peer can request pieces from other peers and upload pieces to them. Unlike a pure client-server system, a peer is not permanently only a client or only a server.', 'Exam')]
story += bullets(['P2P provides self-scalability: a new peer adds demand but can also add upload capacity.', 'Peers may be intermittent and may have changing IP addresses, making management and security difficult.', 'A tracker or distributed discovery helps peers find one another; a central coordination service may still exist even though data transfer is peer-to-peer.', 'In a communication session, the roles are logical and can change. The same peer may be a client while requesting one piece and a server while uploading another.'])
story += [P('Conclusion: the statement that there is no fixed notion of client and server is correct for data exchange in a P2P swarm, although client and server processes can still exist at particular moments.', 'Exam'), P('PYQ 9 | Why HTTP, SMTP, and IMAP use TCP', 'H2x'), P('<b>Answer.</b> HTTP transfers Web objects, SMTP transfers e-mail messages between mail servers, and IMAP retrieves and synchronises messages. All require the application data to arrive without corruption, loss, duplication, or reordering. TCP provides checksum, sequence numbers, acknowledgements, retransmission, ordered byte-stream delivery, flow control, and congestion control. The cost is connection setup and control overhead.', 'Exam'), P('PYQ 10 | Why voice and video may use TCP today', 'H2x'), P('<b>Answer.</b> Real-time voice and video traditionally favour UDP because late data is often less useful than lost data, and UDP avoids retransmission delay. However, many modern services use TCP-based HTTPS streaming, adaptive video over HTTP, or QUIC over UDP. TCP works through NATs and firewalls, provides reliability, and fits Web/CDN infrastructure. DASH can request later chunks at a lower rate when the network is congested. For truly interactive real-time media, UDP or QUIC is often preferred so the application can control delay and loss.', 'Exam'), PageBreak()]

story += [P('PYQ 11 | SMTP e-mail journey through OSI and TCP/IP', 'H2x'), P('<b>Answer.</b> At the sender, Alice writes the message in a user agent. SMTP transfers it to her mail server and later from her mail server to Bob mail server. Bob uses IMAP or Web mail to retrieve it.', 'Exam'), Diagram('email', 'Use this diagram for the e-mail path'), P('OSI trace:', 'H3x')]
story += bullets(['Application: SMTP creates commands and e-mail content; DNS may locate the recipient mail server; IMAP later retrieves the message.', 'Transport: TCP creates a reliable connection, segments the data, numbers bytes, acknowledges received data, and retransmits lost segments.', 'Network: IP encapsulates TCP segments into datagrams and routes them between hosts.', 'Data link: Ethernet or Wi-Fi frames carry each IP datagram across the next link.', 'Physical: copper, fibre, or radio transmits the bits. At each router, the link-layer frame changes for the next hop; the IP datagram continues toward the destination.'])
story += [P('TCP/IP trace:', 'H3x'), P('SMTP or IMAP at application -> TCP at transport -> IP at network -> Ethernet/Wi-Fi at link -> physical bits. The receiver decapsulates in reverse order. The message may pass through a mail server, so there can be one SMTP TCP connection from user agent to sender server, another SMTP connection between mail servers, and an IMAP/HTTPS connection when Bob reads it.', 'Exam'), P('PYQ 12 | Six-node full circuit connectivity', 'H2x'), P('<b>Given:</b> six nodes A, B, C, D, E, F; one dedicated circuit for every pair; setup time 15 seconds per circuit.', 'Exam'), P('Number of circuits = n(n - 1)/2 = 6 x 5 / 2 = 15 circuits', 'Formula'), P('If circuits are established one after another, total setup time = 15 x 15 = 225 seconds. If the switching system can establish all independent circuits in parallel, the elapsed setup time is 15 seconds. Since the question asks total setup time for all circuits, the usual sequential assumption gives 225 seconds; state the assumption.', 'Exam'), P('The 128 Kbps requirement affects capacity reserved per circuit, not the number of pairwise circuits or the sequential setup-time calculation.', 'Exam'), P('PYQ 13 | Go-Back-N and Selective Repeat', 'H2x'), P('<b>Answer.</b> Both are pipelined reliable data-transfer protocols. The sender may transmit several packets before waiting, within a sender window. Sequence numbers identify packets, acknowledgements confirm delivery, and a timer detects loss.', 'Exam'), Diagram('windows', 'Use this diagram with a labelled sender and receiver window'), P('<b>Go-Back-N:</b> the receiver normally accepts only the next in-order packet and sends cumulative ACKs. If packet k is lost, later packets may be discarded or not cumulatively accepted. On timeout, the sender retransmits k and all later unacknowledged packets in the window.', 'Exam'), P('<b>Selective Repeat:</b> the receiver individually acknowledges correct packets and buffers out-of-order packets. When packet k is lost, the sender retransmits only k after its timer expires or a selective negative acknowledgement. SR uses bandwidth more efficiently but requires more receiver storage and more complex bookkeeping.', 'Exam')]

story += [P('PYQ 14 | HTTP request-to-response for non-persistent HTTP', 'H2x'), P('<b>Answer.</b> The user enters a URL. The browser obtains the server IP address using DNS. For the requested object, the browser opens a TCP connection to port 80. The server accepts the connection. The browser sends a GET request containing the URL path. The server returns a response with a status line, headers, and the object. The server closes the TCP connection. For every additional image or object, the browser repeats the process.', 'Exam'), Diagram('http', 'Each object gets its own TCP connection in non-persistent HTTP'), P('For one object, response time is approximately 2RTT + file transmission time: one RTT for TCP setup and one RTT for the HTTP request plus the first response bytes. Persistent HTTP reuses the connection and avoids repeated setup.', 'Exam'), P('PYQ 15 | SMTP sequence and e-mail retrieval', 'H2x'), P('<b>SMTP sequence:</b> TCP connection to port 25 -> server greeting 220 -> client HELO/EHLO -> MAIL FROM -> RCPT TO -> DATA -> headers and body terminated by a line containing a period -> server 250 acceptance -> QUIT -> server 221 closing response.', 'Exam'), P('The receiving mail server stores the message in the recipient mailbox. The recipient uses IMAP to list, read, organise, and delete messages on the server, or uses Web mail where a browser communicates with a Web interface using HTTP/HTTPS.', 'Exam'), P('PYQ 16 | Iterative and recursive DNS for www.example.com', 'H2x'), P('<b>Iterative answer.</b> The client asks its local DNS. If the local server has no cache entry, it asks a root server. The root replies with the .com TLD server. The local server asks the TLD server, which replies with the authoritative server for example.com. The local server asks the authoritative server, receives the A record for www.example.com, caches it, and returns the IP to the client.', 'Exam'), P('<b>Recursive answer.</b> The client asks its local DNS and requests recursion. The local DNS contacts the root, TLD, and authoritative servers on behalf of the client and returns the final address. Recursive service is simpler for the client but places more work on the resolver.', 'Exam'), P('Because the question says no caching, write all hierarchy contacts. If caching were present, the local resolver could answer from an unexpired record and skip some contacts.', 'Exam'), PageBreak()]

story += [P('PYQ 17 | Recommend an ISP tier for a small business', 'H2x'), P('<b>Answer.</b> Recommend a Tier-2 or regional ISP for most small businesses. It usually provides reliable access, support, and adequate bandwidth while buying upstream connectivity from larger providers. A Tier-1 ISP is a global backbone and is expensive and unnecessary unless the business itself needs to provide transit or operate a very large network. A Tier-3 access provider may be sufficient for a small office but may offer less reach or resilience.', 'Exam'), P('The final choice depends on bandwidth, service-level agreement, redundancy, public IP requirements, price, and geographic availability. The key reason is to match the scale of the provider to the scale of the business.', 'Exam'), P('PYQ 18 | BitTorrent client with no data chunks', 'H2x'), P('<b>Answer.</b> The new peer first contacts a tracker or peer-discovery system to obtain a list of peers in the swarm. It opens connections to several peers and learns which pieces each peer has through a bitfield or piece messages. Since it has no pieces, it requests pieces that are available from neighbours, preferably rarest-first to increase diversity. It verifies each downloaded piece using the torrent hash, advertises it, and uploads it to other peers. It uses optimistic unchoking to discover good upload partners. After receiving all pieces, it becomes a seed.', 'Exam'), P('PYQ 19 | TCP versus UDP and applications', 'H2x'), P('<b>TCP:</b> reliable, connection-oriented, in-order byte stream. It uses acknowledgements, retransmissions, flow control, congestion control, and connection setup. Applications: HTTP/HTTPS, SMTP, IMAP, FTP, and many Web transactions.', 'Exam'), P('<b>UDP:</b> connectionless datagrams with low overhead. It does not provide reliability, ordering, flow control, congestion control, timing, or security. Applications: DNS queries, DHCP, real-time games, voice/video systems that choose UDP, and QUIC as a substrate for HTTP/3.', 'Exam'), P('A protocol choice depends on the application. Reliability is useful for files and mail. Low delay and application-controlled loss handling may make UDP or QUIC useful for interactive media.', 'Exam'), P('PYQ 20 | HTTP, SMTP, IMAP, voice, and video transport choice', 'H2x'), P('HTTP, SMTP, and IMAP use TCP because these applications need complete, ordered data. Traditional interactive voice/video often uses UDP because retransmitting late packets can increase delay and cause poor interaction. Modern video-on-demand commonly uses TCP-based HTTP with buffering and adaptive bitrate, while HTTP/3 uses QUIC over UDP. Thus the correct answer recognises both the traditional real-time reason and the current Web/CDN deployment pattern.', 'Exam')]

story += [P('FINAL REVISION SHEET', 'H1x'), P('Definitions to memorise', 'H2x')]
story += bullets(['Protocol: rules for message format, order, and actions.', 'Host/end system: a network-edge device that runs applications and sends or receives data.', 'Forwarding: local movement of a packet from input link to output link.', 'Routing: determination of source-to-destination paths.', 'Transmission delay: time to push packet bits into the link.', 'Propagation delay: time for the signal to travel across the medium.', 'Throughput: delivered bit rate; the bottleneck limits the path.', 'Socket: application-to-transport interface.', 'HTTP: Web request-response protocol.', 'SMTP: server-to-server e-mail transfer protocol.', 'IMAP: server-based e-mail retrieval and synchronisation protocol.', 'DNS: distributed hierarchical name-to-address database and protocol.', 'DASH: adaptive HTTP streaming using encoded chunks and a manifest.', 'CDN: distributed infrastructure that stores content near users.'])
story += [P('Diagrams worth drawing', 'H2x')]
story += bullets(['Internet edge-core diagram with hosts, access networks, and routers.', 'Packet switching versus circuit switching comparison.', 'Four delay components and their formulas.', 'OSI and TCP/IP layer mapping.', 'Encapsulation: message -> segment -> datagram -> frame.', 'Client-server and P2P architecture.', 'HTTP request and response.', 'SMTP mail-server path and IMAP retrieval.', 'DNS root -> TLD -> authoritative hierarchy.', 'DASH client buffer and CDN chunk delivery.', 'Go-Back-N versus Selective Repeat windows.'])
story += [callout('Final exam strategy', 'For a 10-mark answer, spend about one paragraph on the definition, one labelled diagram, three to five numbered working steps, and a short comparison or conclusion. In numerical problems, write the formula, substitute with units, and box the final answer.', HexColor('#EAF7EF'))]

doc = CNDoc(OUT)
doc.build(story)
print(OUT)
