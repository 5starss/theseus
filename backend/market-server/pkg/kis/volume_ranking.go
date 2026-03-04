package kis

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"

	"market-server/internal/domain"
)

// volumeRankItem KIS 거래량 순위 API 응답 단건 (output1 배열 요소)
type volumeRankItem struct {
	Ticker       string `json:"mksc_shrn_iscd"` // 종목코드
	Name         string `json:"hts_kor_isnm"`   // 종목명
	CurrentPrice string `json:"stck_prpr"`      // 현재가
	ChangeRate   string `json:"prdy_ctrt"`      // 전일 대비 등락률
	AccVolume    string `json:"acml_vol"`       // 누적 거래량
}

type volumeRankingResponse struct {
	RtCd    string           `json:"rt_cd"`
	Msg1    string           `json:"msg1"`
	Output1 []volumeRankItem `json:"output1"`
}

// GetVolumeRanking KIS OpenAPI에서 거래량 상위 종목을 조회하여 반환한다.
// tr_id: FHPST01710000 (국내주식 거래량 순위)
func (c *Client) GetVolumeRanking(ctx context.Context, limit int) ([]*domain.Stock, error) {
	data, err := c.DoRequest(
		ctx,
		http.MethodGet,
		"/uapi/domestic-stock/v1/ranking/volume",
		map[string]string{
			"tr_id": "FHPST01710000",
		},
		map[string]string{
			"fid_cond_mrkt_div_code": "J",     // 시장: 주식
			"fid_cond_scr_div_code":  "20171", // 화면번호
			"fid_input_iscd":         "0000",  // 전체 종목
			"fid_div_cls_code":       "0",
			"fid_blng_cls_code":      "0",
			"fid_trgt_cls_code":      "111111111",
			"fid_trgt_exls_cls_code": "000000",
			"fid_input_price_1":      "",
			"fid_input_price_2":      "",
			"fid_vol_cnt":            "",
			"fid_input_date_1":       "",
		},
	)
	if err != nil {
		return nil, fmt.Errorf("kis volume ranking request: %w", err)
	}

	var resp volumeRankingResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return nil, fmt.Errorf("unmarshal volume ranking response: %w", err)
	}

	if resp.RtCd != "0" {
		return nil, fmt.Errorf("kis api error [%s]: %s", resp.RtCd, resp.Msg1)
	}

	// API 응답이 limit보다 적을 수 있으므로 방어 처리
	count := limit
	if len(resp.Output1) < count {
		count = len(resp.Output1)
	}

	stocks := make([]*domain.Stock, 0, count)
	for _, item := range resp.Output1[:count] {
		// KIS 응답은 모두 문자열이므로 타입 변환
		price, _ := strconv.ParseInt(item.CurrentPrice, 10, 64)
		changeRate, _ := strconv.ParseFloat(item.ChangeRate, 64)
		volume, _ := strconv.ParseInt(item.AccVolume, 10, 64)

		stocks = append(stocks, &domain.Stock{
			Ticker:       item.Ticker,
			Name:         item.Name,
			CurrentPrice: price,
			ChangeRate:   changeRate,
			AccVolume:    volume,
		})
	}

	return stocks, nil
}
