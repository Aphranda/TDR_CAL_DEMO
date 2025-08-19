close all
clear all
delete(instrfind)
format long
IS_CALIBRATION = true;

start_freq = 1000; %MHz
stop_freq = 6000; %MHz
step_freq = 100; %MHz

calibration_pow = -20;
calibration_ifbw = 1000; %1KHz

% Command
% SOURce:GPRF:CHANnel1:FREQuency 1000Mhz
% SOURce:GPRF:CHANnel1:WFORm:CW
% SOURce:GPRF:CHANnel1:POWer 0
% SOURce:GPRF:CHANnel1:BWIDth 122.88Mhz
% SOURce:GPRF:CHANnel1:STATe TX
% 配置�?端口CW波，
% SOURce:GPRF:CHANnel1:FREQuency 1000Mhz
% SOURce:GPRF:CHANnel1:WFORm 'Sin1M.sin'
% SOURce:GPRF:CHANnel1:POWer 0
% SOURce:GPRF:CHANnel1:BWIDth 122.88Mhz
% SOURce:GPRF:CHANnel1:STATe TX
% 配置1端口 sin1m.sin


ins_odc = visa('ni', 'TCPIP0::192.168.1.10::7::SOCKET');
fopen(ins_odc);
data = query(ins_odc,'*IDN?');
fprintf(data);
if(IS_CALIBRATION)

    questdlg("Connect The Through of Two port");
    %throughtest%配置Tx ,rx 分开
    %SET 1 PORT OUT, 2 PORT IN
    fprintf(ins_odc,'SOURce:GPRF:CHANnel1:STATe %s\n',"TRXD");
    fprintf(ins_odc,'SOURce:GPRF:CHANnel2:STATe %s\n',"TRXD");
    fprintf(ins_odc,"SOURce:GPRF:CHANnel1:WFORm 'Sin1M.sin'\n");
    %fprintf(ins_odc,"SOURce:GPRF:CHANnel2:WFORm 'Sin1M.sin'\n");
    test_cnt = 1;
    data = "";
    for freq = start_freq:step_freq:stop_freq
        fprintf(ins_odc,"SOURce:GPRF:CHANnel1:FREQuency %.2fMhz\n",freq);
        fprintf(ins_odc,"SOURce:GPRF:CHANnel1:POWer %.2f\n",calibration_pow);
        fprintf(ins_odc,"SOURce:GPRF:CHANnel2:POWer %.2f\n",-70);
        %M10 , S11M
        data = sprintf("READ:GPRF:CHANnel1:POWer:GPRM? %.2fms",1000/calibration_ifbw);
        value = query(ins_odc,data);
        TEST_LOG_M10(test_cnt)= str2double(value)-calibration_pow;
        fprintf("LOG_M10 freq = " + freq +  "  " + value);
        data = sprintf("CALIbration:INSTrument:PHASe  TX1,RX1,%d",122880*1000/calibration_ifbw);
        value = query(ins_odc,data);
        fprintf("PHASE_M10 freq = " + freq +  "  " + value);
        TEST_PHASE_M10(test_cnt) = str2double(value);
        DATA_M10(test_cnt) = 10^(TEST_LOG_M10(test_cnt)/20)*exp(TEST_PHASE_M10(test_cnt)/180*pi*1i);

        %M9 , S21M
        data = sprintf("READ:GPRF:CHANnel2:POWer:GPRM? %.2fms",1000/calibration_ifbw);
        value = query(ins_odc,data);
        fprintf("LOG_M9 freq = " + freq +  "  " + value);
        TEST_LOG_M9(test_cnt) = str2double(value)-calibration_pow;
        data = sprintf("CALIbration:INSTrument:PHASe  TX1,RX2,%d",122880*1000/calibration_ifbw);
        value = query(ins_odc,data);
        fprintf("PHASE_M9 freq = " + freq +  "  " + value);
        TEST_PHASE_M9(test_cnt) = str2double(value);

        DATA_M9(test_cnt) = 10^(TEST_LOG_M9(test_cnt)/20)*exp(TEST_PHASE_M9(test_cnt)/180*pi*j);
        test_cnt = test_cnt + 1;
    end

    %throughtest�? SET 2 PORT OUT, 1 PORT IN
    test_cnt = 1;
    for freq = start_freq:step_freq:stop_freq
        flushinput(ins_odc);
        fprintf(ins_odc,"SOURce:GPRF:CHANnel2:FREQuency %.2fMhz\n",freq);
        
        fprintf(ins_odc,"SOURce:GPRF:CHANnel2:POWer %.2f\n",calibration_pow);
        fprintf(ins_odc,"SOURce:GPRF:CHANnel1:POWer %.2f\n",-70);
        %M12 , S22M
        fprintf(ins_odc,"READ:GPRF:CHANnel2:POWer:GPRM? %.2fms\n",1000/calibration_ifbw);
        TEST_LOG_M12(test_cnt)= str2double(fscanf(ins_odc))-calibration_pow;
        fprintf(ins_odc,"CALIbration:INSTrument:PHASe  TX1,RX2,%d\n",122880*1000/calibration_ifbw);
        TEST_PHASE_M12(test_cnt) = str2double(fscanf(ins_odc));
        DATA_M12(test_cnt) = 10^(TEST_LOG_M12(test_cnt)/20)*exp(TEST_PHASE_M12(test_cnt)/180*pi*j);

        %M11 , S12M
        fprintf(ins_odc,"READ:GPRF:CHANnel1:POWer:GPRM? %.2fms\n",1000/calibration_ifbw);
        TEST_LOG_M11(test_cnt) = str2double(fscanf(ins_odc))-calibration_pow;
        fprintf(ins_odc,"CALIbration:INSTrument:PHASe  TX1,RX1,%d\n",122880*1000/calibration_ifbw);
        TEST_PHASE_M11(test_cnt) = str2double(fscanf(ins_odc));

        DATA_M11(test_cnt) = 10^(TEST_LOG_M11(test_cnt)/20)*exp(TEST_PHASE_M11(test_cnt)/180*pi*j);

        test_cnt = test_cnt + 1;
    end


    questdlg("Connect The PORT1 to OPEN, PORT2 to LOAD");
    %OPEN TEST, PORT 1 OPEN,  PORT2  LOAD
    %SET 1, TX,  SET 2 RX
    test_cnt = 1;
    for freq = start_freq:step_freq:stop_freq
        fprintf(ins_odc,"SOURce:GPRF:CHANnel1:FREQuency %.2fMhz\n",freq);
        
        fprintf(ins_odc,"SOURce:GPRF:CHANnel1:POWer %.2f\n",calibration_pow);
        fprintf(ins_odc,"SOURce:GPRF:CHANnel2:POWer %.2f\n",-70);
        %M3 , S11M
        fprintf(ins_odc,"READ:GPRF:CHANnel1:POWer:GPRM? %.2fms\n",1000/calibration_ifbw);
        TEST_LOG_M3(test_cnt)= str2double(fscanf(ins_odc))-calibration_pow;
        fprintf(ins_odc,"CALIbration:INSTrument:PHASe  TX1,RX1,%d\n",122880*1000/calibration_ifbw);
        TEST_PHASE_M3(test_cnt) = str2double(fscanf(ins_odc));
        DATA_M3(test_cnt) = 10^(TEST_LOG_M3(test_cnt)/20)*exp(TEST_PHASE_M3(test_cnt)/180*pi*j);

        %M6 , S21M
        fprintf(ins_odc,"READ:GPRF:CHANnel2:POWer:GPRM? %.2fms\n",1000/calibration_ifbw);
        TEST_LOG_M6(test_cnt) = str2double(fscanf(ins_odc))-calibration_pow;
        fprintf(ins_odc,"CALIbration:INSTrument:PHASe  TX1,RX2,%d\n",122880*1000/calibration_ifbw);
        TEST_PHASE_M6(test_cnt) = str2double(fscanf(ins_odc));

        DATA_M6(test_cnt) = 10^(TEST_LOG_M6(test_cnt)/20)*exp(TEST_PHASE_M6(test_cnt)/180*pi*j);

        test_cnt = test_cnt + 1;
        pause(0.1)
    end

    %OPEN TEST, PORT 1 OPEN,  PORT2  LOAD
    %SET 2, TX,  SET 2 RX
    test_cnt = 1;
    for freq = start_freq:step_freq:stop_freq
        fprintf(ins_odc,"SOURce:GPRF:CHANnel2:FREQuency %.2fMhz\n",freq);
        
        fprintf(ins_odc,"SOURce:GPRF:CHANnel2:POWer %.2f\n",calibration_pow);
        fprintf(ins_odc,"SOURce:GPRF:CHANnel1:POWer %.2f\n",-70);
        %M7 , S22M
        fprintf(ins_odc,"READ:GPRF:CHANnel2:POWer:GPRM? %.2fms\n",1000/calibration_ifbw);
        TEST_LOG_M7(test_cnt)= str2double(fscanf(ins_odc))-calibration_pow;
        fprintf(ins_odc,"CALIbration:INSTrument:PHASe  TX1,RX2,%d\n",122880*1000/calibration_ifbw);
        TEST_PHASE_M7(test_cnt) = str2double(fscanf(ins_odc));
        DATA_M7(test_cnt) = 10^(TEST_LOG_M7(test_cnt)/20)*exp(TEST_PHASE_M7(test_cnt)/180*pi*j);

        test_cnt = test_cnt + 1;
        pause(0.1)
    end
    
    
    questdlg("Connect The PORT1 to SHORT, PORT2 to LOAD");
    %SHORT TEST%配置Tx ,rx 分开
    %PORT1 SHORT, PORT 2 LOAD
    %SET 1 PORT OUT, 1 PORT IN
    test_cnt = 1;
    for freq = start_freq:step_freq:stop_freq
        fprintf(ins_odc,"SOURce:GPRF:CHANnel1:FREQuency %.2fMhz\n",freq);
        
        fprintf(ins_odc,"SOURce:GPRF:CHANnel1:POWer %.2f\n",calibration_pow);
        fprintf(ins_odc,"SOURce:GPRF:CHANnel2:POWer %.2f\n",-70);

        %M1 , S11M
        fprintf(ins_odc,"READ:GPRF:CHANnel1:POWer:GPRM? %.2fms\n",1000/calibration_ifbw);
        TEST_LOG_M1(test_cnt)= str2double(fscanf(ins_odc))-calibration_pow;
        fprintf(ins_odc,"CALIbration:INSTrument:PHASe  TX1,RX1,%d\n",122880*1000/calibration_ifbw);
        TEST_PHASE_M1(test_cnt) = str2double(fscanf(ins_odc));
        DATA_M1(test_cnt) = 10^(TEST_LOG_M1(test_cnt)/20)*exp(TEST_PHASE_M1(test_cnt)/180*pi*j);

        test_cnt = test_cnt + 1;
        pause(0.1)
    end




    questdlg("Connect The PORT2 to OPEN, PORT1 to LOAD");
    %OPEN TEST, PORT 2 OPEN,  PORT1  LOAD
    %SET 2, TX,  SET 1 RX
    test_cnt = 1;
    for freq = start_freq:step_freq:stop_freq
        fprintf(ins_odc,"SOURce:GPRF:CHANnel2:FREQuency %.2fMhz\n",freq);
        
        fprintf(ins_odc,"SOURce:GPRF:CHANnel2:POWer %.2f\n",calibration_pow);
        fprintf(ins_odc,"SOURce:GPRF:CHANnel1:POWer %.2f\n",-70);
        %M4 , S22M
        fprintf(ins_odc,"READ:GPRF:CHANnel2:POWer:GPRM? %.2fms\n",1000/calibration_ifbw);
        TEST_LOG_M4(test_cnt)= str2double(fscanf(ins_odc))-calibration_pow;
        fprintf(ins_odc,"CALIbration:INSTrument:PHASe  TX1,RX2,%d\n",122880*1000/calibration_ifbw);
        TEST_PHASE_M4(test_cnt) = str2double(fscanf(ins_odc));
        DATA_M4(test_cnt) = 10^(TEST_LOG_M4(test_cnt)/20)*exp(TEST_PHASE_M4(test_cnt)/180*pi*j);

        %M8 , S12M
        fprintf(ins_odc,"READ:GPRF:CHANnel1:POWer:GPRM? %.2fms\n",1000/calibration_ifbw);
        TEST_LOG_M8(test_cnt) = str2double(fscanf(ins_odc))-calibration_pow;
        fprintf(ins_odc,"CALIbration:INSTrument:PHASe  TX1,RX1,%d\n",122880*1000/calibration_ifbw);
        TEST_PHASE_M8(test_cnt) = str2double(fscanf(ins_odc));

        DATA_M8(test_cnt) = 10^(TEST_LOG_M8(test_cnt)/20)*exp(TEST_PHASE_M8(test_cnt)/180*pi*j);

        test_cnt = test_cnt + 1;
        pause(0.1)
    end

    %OPEN TEST, PORT 2 OPEN,  PORT1  LOAD
    %SET 1, TX,  SET 1 RX
    test_cnt = 1;
    for freq = start_freq:step_freq:stop_freq
        fprintf(ins_odc,"SOURce:GPRF:CHANnel1:FREQuency %.2fMhz\n",freq);
        
        fprintf(ins_odc,"SOURce:GPRF:CHANnel1:POWer %.2f\n",calibration_pow);
        fprintf(ins_odc,"SOURce:GPRF:CHANnel2:POWer %.2f\n",-70);
        %M5 , S11M
        fprintf(ins_odc,"READ:GPRF:CHANnel1:POWer:GPRM? %.2fms\n",1000/calibration_ifbw);
        TEST_LOG_M5(test_cnt)= str2double(fscanf(ins_odc))-calibration_pow;
        fprintf(ins_odc,"CALIbration:INSTrument:PHASe  TX1,RX1,%d\n",122880*1000/calibration_ifbw);
        TEST_PHASE_M5(test_cnt) = str2double(fscanf(ins_odc));
        DATA_M5(test_cnt) = 10^(TEST_LOG_M5(test_cnt)/20)*exp(TEST_PHASE_M5(test_cnt)/180*pi*j);

        test_cnt = test_cnt + 1;
        pause(0.1)
    end


    questdlg("Connect The PORT2 to SHORT, PORT1 to LOAD");
    %SHORT TEST%配置Tx ,rx 分开
    %PORT2 SHORT, PORT 1 LOAD
    %SET 2 PORT OUT, 2 PORT IN
    test_cnt = 1;
    for freq = start_freq:step_freq:stop_freq
        fprintf(ins_odc,"SOURce:GPRF:CHANnel2:FREQuency %.2fMhz\n",freq);
        
        fprintf(ins_odc,"SOURce:GPRF:CHANnel2:POWer %.2f\n",calibration_pow);
        fprintf(ins_odc,"SOURce:GPRF:CHANnel1:POWer %.2f\n",-70);

        %M2 , S22M
        fprintf(ins_odc,"READ:GPRF:CHANnel2:POWer:GPRM? %.2fms\n",1000/calibration_ifbw);
        TEST_LOG_M2(test_cnt)= str2double(fscanf(ins_odc))-calibration_pow;
        fprintf(ins_odc,"CALIbration:INSTrument:PHASe  TX1,RX2,%d\n",122880*1000/calibration_ifbw);
        TEST_PHASE_M2(test_cnt) = str2double(fscanf(ins_odc));
        DATA_M2(test_cnt) = 10^(TEST_LOG_M2(test_cnt)/20)*exp(TEST_PHASE_M2(test_cnt)/180*pi*j);

        test_cnt = test_cnt + 1;
        pause(0.1)
    end


    for i=1:1:length(DATA_M2)
       EDF(i) =  DATA_M5(i);
       ERF(i) =  2*(DATA_M5(i)-DATA_M1(i))*(DATA_M3(i)-DATA_M5(i))/(DATA_M3(i)-DATA_M1(i));
       ESF(i) = (DATA_M3(i)+DATA_M1(i)-2*DATA_M5(i))/(DATA_M3(i)-DATA_M1(i));
       EXF(i) = DATA_M6(i);
       ELF(i) = (DATA_M10(i)-DATA_M5(i))/(ESF(i)*(DATA_M10(i)-DATA_M5(i))+ERF(i));
       ETF(i) = (DATA_M9(i)-DATA_M6(i))*(1-ESF(i)*ELF(i));

       EDR(i) =  DATA_M7(i);
       ERR(i) =  2*(DATA_M7(i)-DATA_M2(i))*(DATA_M4(i)-DATA_M7(i))/(DATA_M4(i)-DATA_M2(i));
       ESR(i) = (DATA_M4(i)+DATA_M2(i)-2*DATA_M7(i))/(DATA_M4(i)-DATA_M2(i));
       EXR(i) = DATA_M8(i);
       ELR(i) = (DATA_M12(i)-DATA_M7(i))/(ESR(i)*(DATA_M12(i)-DATA_M7(i))+ERR(i));
       ETR(i) = (DATA_M11(i)-DATA_M8(i))*(1-ESR(i)*ELR(i));
    end
end
    %make test
    questdlg("Please make connections");
    %SET 1 PORT OUT, 2 PORT IN
    test_cnt = 1;
    for freq = start_freq:step_freq:stop_freq
        fprintf(ins_odc,"SOURce:GPRF:CHANnel1:FREQuency %.2fMhz\n",freq);
        
        fprintf(ins_odc,"SOURce:GPRF:CHANnel1:POWer %.2f\n",calibration_pow);
        fprintf(ins_odc,"SOURce:GPRF:CHANnel2:POWer %.2f\n",-70);

        %test S11M
        fprintf(ins_odc,"READ:GPRF:CHANnel1:POWer:GPRM? %.2fms\n",1000/calibration_ifbw);
        TEST_LOG_TEST_S11M(test_cnt)= str2double(fscanf(ins_odc))-calibration_pow;
        fprintf(ins_odc,"CALIbration:INSTrument:PHASe  TX1,RX1,%d\n",122880*1000/calibration_ifbw);
        TEST_PHASE_TEST_S11M(test_cnt) = str2double(fscanf(ins_odc));
        RESULT_S11(test_cnt) = 10^(TEST_LOG_TEST_S11M(test_cnt)/20)*exp(TEST_PHASE_TEST_S11M(test_cnt)/180*pi*j);

        %M9 , S21M
        fprintf(ins_odc,"READ:GPRF:CHANnel2:POWer:GPRM? %.2fms\n",1000/calibration_ifbw);
        TEST_LOG_TEST_S12M(test_cnt) = str2double(fscanf(ins_odc))-calibration_pow;
        fprintf(ins_odc,"CALIbration:INSTrument:PHASe  TX1,RX2,%d\n",122880*1000/calibration_ifbw);
        TEST_PHASE_TEST_S12M(test_cnt) = str2double(fscanf(ins_odc));

        RESULT_S21(test_cnt) = 10^(TEST_LOG_TEST_S12M(test_cnt)/20)*exp(TEST_PHASE_TEST_S12M(test_cnt)/180*pi*j);

        test_cnt = test_cnt + 1;
        pause(0.1)
    end

    %throughtest�? SET 2 PORT OUT, 1 PORT IN
    test_cnt = 1;
    for freq = start_freq:step_freq:stop_freq
        fprintf(ins_odc,"SOURce:GPRF:CHANnel1:FREQuency %.2fMhz\n",freq);
        
        fprintf(ins_odc,"SOURce:GPRF:CHANnel2:POWer %.2f\n",calibration_pow);
        fprintf(ins_odc,"SOURce:GPRF:CHANnel1:POWer %.2f\n",-70);
        % S22M
        fprintf(ins_odc,"READ:GPRF:CHANnel2:POWer:GPRM? %.2fms\n",1000/calibration_ifbw);
        TEST_LOG_TEST_S22M(test_cnt)= str2double(fscanf(ins_odc))-calibration_pow;
        fprintf(ins_odc,"CALIbration:INSTrument:PHASe  TX1,RX2,%d\n",122880*1000/calibration_ifbw);
        TEST_PHASE_TEST_S22M(test_cnt) = str2double(fscanf(ins_odc));
        RESULT_S22(test_cnt) = 10^(TEST_LOG_TEST_S22M(test_cnt)/20)*exp(TEST_PHASE_TEST_S22M(test_cnt)/180*pi*j);

        % S12M
        fprintf(ins_odc,"READ:GPRF:CHANnel1:POWer:GPRM? %.2fms\n",1000/calibration_ifbw);
        TEST_LOG_TEST_S21M(test_cnt) = str2double(fscanf(ins_odc))-calibration_pow;
        fprintf(ins_odc,"CALIbration:INSTrument:PHASe  TX1,RX1,%d\n",122880*1000/calibration_ifbw);
        TEST_PHASE_TEST_S21M(test_cnt) = str2double(fscanf(ins_odc));

        RESULT_S12(test_cnt) = 10^(TEST_LOG_TEST_S21M(test_cnt) /20)*exp(TEST_PHASE_TEST_S21M(test_cnt) /180*pi*j);

        test_cnt = test_cnt + 1;
        pause(0.1)
    end

if(IS_CALIBRATION)
    %make calibration and calculate results
    A = (RESULT_S11 - EDF)./ERF;
    B = (RESULT_S21 - EXF)./ETF;
    C = (RESULT_S12 - EXR)./ETR;
    D = (RESULT_S22 - EDR)./ERR;

    MEASURED_S11 = (A.*(1+D.*ESR)-B.*C.*ELF)./((1+A.*ESF).*(1+D.*ESR)-B.*C.*ELF.*ELR);
    MEASURED_S22 = (D.*(1+A.*ESF)-B.*C.*ELR)./((1+A.*ESF).*(1+D.*ESR)-B.*C.*ELF.*ELR);
    MEASURED_S12 = (C.*(1+A.*(ESF-ELR)))./((1+A.*ESF).*(1+D.*ESR)-B.*C.*ELF.*ELR);
    MEASURED_S21 = (B.*(1+D.*(ESR-ELF)))./((1+A.*ESF).*(1+D.*ESR)-B.*C.*ELF.*ELR);
    
else
    MEASURED_S11 = RESULT_S11;
    MEASURED_S12 = RESULT_S12;
    MEASURED_S21 = RESULT_S21;
    MEASURED_S22 = RESULT_S22;
end




figure(1);
subplot(2,2,1);
plot(1:1:length(RESULT_S11),20*log10(abs(RESULT_S11)),1:1:length(MEASURED_S11),20*log10(abs(MEASURED_S11)));
subplot(2,2,2);
plot(1:1:length(RESULT_S21),20*log10(abs(RESULT_S21)),1:1:length(MEASURED_S21),20*log10(abs(MEASURED_S21)));
subplot(2,2,3);
plot(1:1:length(RESULT_S12),20*log10(abs(RESULT_S12)),1:1:length(MEASURED_S12),20*log10(abs(MEASURED_S12)));
subplot(2,2,4);
plot(1:1:length(RESULT_S22),20*log10(abs(RESULT_S22)),1:1:length(MEASURED_S22),20*log10(abs(MEASURED_S22)));

fclose(ins_odc);